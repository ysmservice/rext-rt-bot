# RT - Player Pool

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias, TypeVar, Generic, Any
from collections.abc import Callable

from collections import defaultdict

from discord.ext import tasks
import discord

from pydub import AudioSegment

from data import DATA
from rtlib.common.reply_error import BadRequest

if TYPE_CHECKING:
    from .bot import RT


AfterFunction: TypeAlias = Callable[[Exception | None], Any]
VoiceChannel: TypeAlias = discord.VoiceChannel | discord.StageChannel
if not TYPE_CHECKING:
    # 型チェッカーでおかしいことに何ないようにここでDiscord用の`AudioSegment`になるように`AudioSegment`をラップする。
    _original_audio_segment = AudioSegment
    AudioSegment = lambda *args, **kwargs: _original_audio_segment(
        *args, sample_width=discord.opus._OpusStruct.SAMPLE_SIZE
            // discord.opus._OpusStruct.CHANNELS,
        frame_rate=discord.opus._OpusStruct.SAMPLING_RATE,
        channels=discord.opus._OpusStruct.CHANNELS, **kwargs
    )
SILENT_DATA = AudioSegment(
    b"\0\0" * discord.opus._OpusStruct.CHANNELS
        * int((0.02) * discord.opus._OpusStruct.SAMPLING_RATE)
)
"無音データです。"


ControllerSourceT = TypeVar("ControllerSourceT", bound=discord.AudioSource)
class Controller(Generic[ControllerSourceT]):
    "音源の操作をするためのコントローラーです。"

    def __init__(self, group: str, tag: str, source: ControllerSourceT, after: AfterFunction):
        self.group, self.tag, self.source = group, tag, source
        self.is_stopped = False
        self.is_paused = False
        self.after = after

    def stop(self) -> None:
        "音源の再生を停止します。"
        self.is_stopped = True

    def toggle_pause(self) -> bool:
        "一時停止をするまたはやめます。"
        self.is_paused = not self.is_paused
        return self.is_paused


SourceT = TypeVar("SourceT", bound=discord.AudioSource)
class MixinAudioSource(discord.AudioSource, Generic[SourceT]):
    """音声をミックスできるようにした`discord.AudioSource`です。
    これでミックスするオーディオソースはOpusでエンコードされていないデータを返す必要があります。"""

    def __init__(self, *args: Any, **kwargs: Any):
        self.controllers = defaultdict[str, dict[str, Controller[SourceT]]](dict)
        super().__init__(*args, **kwargs)

    def is_opus(self) -> bool:
        return False

    def read(self) -> bytes:
        # 全ての音声のデータを取り出す。
        data = SILENT_DATA
        for group in set(self.controllers.keys()):
            for controller in set(self.controllers[group].values()):
                # もし音源が再生停止となっているのなら止める。
                if controller.is_stopped:
                    self.cleanup_source(controller, None)
                    continue
                # もし音源が一時停止中なら、音声データを読み込まないで無音データを代わりに重ねる。
                if controller.is_paused:
                    continue
                # 音声を重ねる。
                error = False
                try:
                    if (new := controller.source.read()):
                        data = data.overlay(AudioSegment(new))
                    else:
                        error = None
                except Exception as e:
                    error = e
                # 使い終わったまたはエラーしたソースはお片付けする。
                if error is not False:
                    self.cleanup_source(controller, error)

        return data.raw_data if self.controllers else bytes()

    def cleanup_source(self, controller: Controller, error: Exception | None) -> None:
        "音源のお片付けをします。"
        controller.source.cleanup()
        controller.after(error)
        del self.controllers[controller.group][controller.tag]
        if not self.controllers[controller.group]:
            del self.controllers[controller.group]

    def cleanup(self) -> None:
        "このクラスのインスタンスのお片付けをします。"
        for group in set(self.controllers.keys()):
            for controller in set(self.controllers[group].values()):
                self.cleanup_source(controller, None)


MixerSourceT = TypeVar("MixerSourceT", bound=discord.AudioSource)
class Mixer(Generic[MixerSourceT]):
    "複数の音源を重ねて再生をするということを簡単に行うためのクラスです。"

    def __init__(self, pool: MixerPool, vc: discord.VoiceClient):
        self.pool, self.vc = pool, vc
        self.now = MixinAudioSource[MixerSourceT]()

    def play(
        self, group: str, tag: str, source: MixerSourceT,
        after: AfterFunction = lambda _: None,
    ) -> None:
        """音源を再生します。既に何かしら音源が再生されている場合でも重ねて再生されます。
        `group`引数は音源を提供する元を識別するためのグループ名を入れてください。
        例えば、音楽プレイヤーの場合は`"Music"`などが良いでしょう。
        `tag`引数は音源を識別するための名前です。"""
        play = not self.now.controllers
        self.now.controllers[group][tag] = Controller(group, tag, source, after)
        # もしまだ再生を行なっていないのなら再生を始める。
        if play:
            self.vc.play(self.now)

    def get_controllers(self, group: str) -> dict[str, Controller]:
        "指定されたグループの音源のコントローラーを返します。"
        return self.now.controllers[group]

    def is_playing(self, group: str) -> bool:
        "指定されたグループから提供されている音源が再生されているかどうかを返します。"
        return group in self.now.controllers


class MixerPool:
    "Mixerのプールです。自動切断等も行います。"

    def __init__(self, bot: RT):
        self.bot = bot
        self._try_loaded = False
        self.mixers: dict[VoiceChannel, Mixer] = {}
        self._auto_disconnect.start()

    def _try_load_opus(self) -> None:
        if not self._try_loaded:
            if not discord.opus.is_loaded():
                discord.opus.load_opus(DATA["opus"])
            self._try_loaded = True

    async def acquire(self, channel: VoiceChannel) -> Mixer:
        "音声プレイヤーを取得します。これを実行すると自動でボイスチャンネルに接続をします。"
        self._try_load_opus()
        if channel not in self.mixers:
            self.mixers[channel] = Mixer(self, await channel.connect())
        return self.mixers[channel]

    async def release(self, obj: VoiceChannel | Mixer, *args: Any, **kwargs: Any) -> None:
        "音声プレイヤーを終了させます。"
        player = obj if isinstance(obj, Mixer) else self.mixers[obj]
        player.vc.cleanup()
        await player.vc.disconnect(*args, **kwargs)
        self.bot.dispatch("release_player", player)
        del self.mixers[player.vc.channel]

    def get_voice_channel(self, member: discord.Member) -> VoiceChannel:
        "メンバーオブジェクトからボイスチャンネルを取得します。"
        if member.voice is None or member.voice.channel is None:
            raise BadRequest({
                "ja": "どこに接続すれば良いかわかりません。",
                "en": "I do not know where to connect."
            })
        return member.voice.channel

    async def acquire_by_member(self, member: discord.Member) -> Mixer:
        "メンバーオブジェクトから接続先を探して、接続可能かを確かめてから音声プレイヤーを取得します。"
        if any(channel.guild.id == member.guild.id for channel in self.mixers.keys()):
            raise BadRequest({
                "ja": "既に音声再生が他のチャンネルで使われています。",
                "en": "I do not know where to connect."
            })
        return await self.acquire(self.get_voice_channel(member))

    async def release_by_member(self, member: discord.Member, *args: Any, **kwargs: Any) -> None:
        "メンバーオブジェクトから接続している場所を探して、接続先のMixerのお片付けをします。"
        await self.release(self.get_voice_channel(member), *args, **kwargs)

    def close(self) -> None:
        self._auto_disconnect.cancel()

    @tasks.loop(seconds=30)
    async def _auto_disconnect(self):
        for channel in set(self.mixers.keys()):
            # 参加しているボイスチャンネルにいるユーザー全員Botなら切断を行う。
            if all(member.bot for member in channel.members):
                await self.release(channel)