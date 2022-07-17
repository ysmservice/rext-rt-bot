# RT - Player Pool

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias, TypeVar, Generic, Any
from collections.abc import Callable

from concurrent.futures import ThreadPoolExecutor

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


SourceT = TypeVar("SourceT", bound=discord.AudioSource)
class MixinAudioSource(discord.AudioSource, Generic[SourceT]):
    """音声をミックスできるようにした`discord.AudioSource`です。
    これでミックスするオーディオソースはOpusでエンコードされていないデータを返す必要があります。"""

    def __init__(self, *args: Any, **kwargs: Any):
        self.sources: dict[str, SourceT] = {}
        self.paused = set[str]()
        self._remove_queues = set[str]()
        self.before = 0.0
        super().__init__(*args, **kwargs)

    def is_opus(self) -> bool:
        return False

    def read(self) -> bytes:
        # 削除キューにある音源を削除する。
        for queue in self._remove_queues:
            self.cleanup_source(queue, None)
        self._remove_queues.clear()

        # 全ての音声のデータを取り出す。
        data = SILENT_DATA
        for tag, source in set(self.sources.items()):
            # もしソースが一時停止中なら、音声データを読み込まないで無音データを代わりに重ねる。
            if tag in self.paused:
                data = data.overlay(SILENT_DATA)
                continue
            # 音声を重ねる。
            error = False
            try:
                if (new := source.read()):
                    data = data.overlay(AudioSegment(new))
                else:
                    error = None
            except Exception as e:
                error = e
            # 使い終わったまたはエラーしたソースはお片付けする。
            if error is not False:
                self.cleanup_source(tag, error)

        return data.raw_data if self.sources else bytes()

    def cleanup_source(self, tag: str, error: Exception | None):
        "音源のお片付けをします。"
        self.sources[tag].cleanup()
        getattr(self.sources[tag], "_after")(error)
        del self.sources[tag]

    def cleanup(self) -> None:
        "このクラスのインスタンスのお片付けをします。"
        for tag in set(self.sources.keys()):
            self.cleanup_source(tag, None)


MixerSourceT = TypeVar("MixerSourceT", bound=discord.AudioSource)
class Mixer(Generic[MixerSourceT]):
    "複数の音源を重ねて再生をするということを簡単にするためのクラスです。"

    now: MixinAudioSource[MixerSourceT] | None = None

    def __init__(self, pool: MixerPool, vc: discord.VoiceClient):
        self.pool, self.vc = pool, vc

    def play(
        self, tag: str, source: MixerSourceT,
        after: AfterFunction = lambda _: None,
    ) -> None:
        "音源を追加します。まだ何も再生していない場合は自動で再生が始まります。"
        if self.now is None:
            self.now = MixinAudioSource()
        play = not self.now.sources
        setattr(source, "_after", after)
        self.now.sources[tag] = source
        # もしまだ再生を行なっていないのなら再生を始める。
        if play:
            self.vc.play(self.now)

    def _check(self) -> None:
        if self.now is None:
            raise KeyError("その音源が見つかりませんでした。")

    def remove_source(self, tag: str) -> None:
        "音源を削除します。"
        self._check()
        assert self.now is not None
        self.now._remove_queues.add(tag)

    def toggle_pause_source(self, tag: str) -> bool:
        """指定されたタグの音源の再生の一時停止するまたはやめます。
        帰ってきた値が`True`の場合は止めたということになります。"""
        self._check()
        assert self.now is not None
        if tag in self.now.paused:
            self.now.paused.remove(tag)
            return False
        else:
            self.now.paused.add(tag)
            return True


class MixerPool:
    "Mixerのプールです。自動切断等も行います。"

    def __init__(self, bot: RT):
        self.bot = bot
        self._try_loaded = False
        self.mixers: dict[VoiceChannel, Mixer] = {}
        self._auto_disconnect.start()
        self.executor = ThreadPoolExecutor(3, thread_name_prefix="ThreadForVoiceFeatures")

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
        self.executor.shutdown()
        self._auto_disconnect.cancel()

    @tasks.loop(seconds=30)
    async def _auto_disconnect(self):
        for channel in set(self.mixers.keys()):
            # 参加しているボイスチャンネルにいるユーザー全員Botなら切断を行う。
            if all(member.bot for member in channel.members):
                await self.release(channel)