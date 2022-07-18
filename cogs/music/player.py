# RT Music - Player

from __future__ import annotations

from typing import TYPE_CHECKING

from random import sample
from enum import Enum

import discord

from core import t
from core.general import Cog

from rtlib.common.utils import make_error_message, code_block

if TYPE_CHECKING:
    from core.mixer_pool import Mixer, Controller

    from .__init__ import MusicCog
    from .music import Music


class LoopMode(Enum):
    "ループのモードの設定です。"

    NONE = 1
    ALL = 2
    ONE = 4


class MusicPlayer:
    "音楽プレイヤーです。"

    def __init__(
        self, cog: MusicCog, player: Mixer[discord.PCMVolumeTransformer],
        sendable: discord.TextChannel | discord.VoiceChannel
    ):
        self.cog, self.mixer, self.sendable = cog, player, sendable
        self.queue: list[Music] = []

        self._volume = 0.8

    async def play(self) -> None:
        "音楽再生をします。キューの一番最初のものを再生します。"
        music = self.queue[0]
        music.start()
        source = await music.make_source()
        source.volume = self.volume
        self.mixer.play(
            self.cog.__cog_name__, music.tag, source,
            lambda e: self.cog.bot.loop.create_task(self._after(e))
        )

    async def _after(self, error: Exception | None) -> None:
        # 再生終了後に呼び出されるメソッドです。
        last = self.queue.pop(0)
        last.close()

        # エラーがあるのならそれを報告する。
        if error is not None:
            await self.sendable.send(t(dict(
                ja="{name}の再生に失敗しました。\nエラーコード：{error}",
                en="Failed to play {name}.\nErrorCode: {error}"
            ), last.author, name=last.title, error=code_block(
                make_error_message(error), "python"
            )), allowed_mentions=discord.AllowedMentions.none())

        if not self.cog.bot.is_closing() and self.queue:
            await self.play()

    @property
    def controllers(self) -> dict[str, Controller[discord.PCMVolumeTransformer]]:
        return self.mixer.get_controllers(self.cog.__cog_name__)

    @property
    def now(self) -> Music | None:
        if self.queue:
            return self.queue[0]

    @property
    def now_controller(self) -> Controller[discord.PCMVolumeTransformer] | None:
        if self.now is not None:
            return self.controllers.get(self.now.tag)

    def is_playing(self) -> bool:
        "現在再生を行なっているかどうかを返します。"
        return self.mixer.is_playing(self.cog.__cog_name__)

    def _check_now(self) -> None:
        if self.now is None:
            raise Cog.reply_error.BadRequest({
                "ja": "現在何も再生していません。",
                "en": "Nothing is currently playing."
            })

    def toggle_pause(self) -> bool:
        "一時停止の切り替えをします。"
        self._check_now()
        assert self.now_controller is not None
        return self.now_controller.toggle_pause()

    def skip(self) -> None:
        "スキップをします。"
        self._check_now()
        assert self.now_controller is not None
        self.now_controller.stop()

    @property
    def length(self) -> int:
        "キューの長さを取得します。"
        return len(self.queue)

    def loop(self, mode: LoopMode | None) -> LoopMode:
        "ループを設定します。"
        if mode is None:
            if self._loop == LoopMode.NONE:
                self._loop = LoopMode.ONE
            elif self._loop == LoopMode.ONE:
                self._loop = LoopMode.ALL
            else:
                self._loop = LoopMode.NONE
        else:
            self._loop = mode
        return self._loop

    @property
    def volume(self) -> float:
        """音量を取得します。
        代入することで音量の変更をすることができます。
        再生中の音源の音量も変更されます。"""
        return self._volume

    @volume.setter
    def volume(self, volume: float):
        self._volume = volume
        # もし音楽の再生中なら再生中のものの音量を変更する。
        if self.now is not None:
            assert self.now_controller is not None
            self.now_controller.source.volume = self._volume

    def shuffle(self):
        "キューをシャッフルします。"
        if self.queue:
            self.queue[1:] = sample(self.queue[1:], len(self.queue[1:]))

    def __str__(self):
        return f"<MusicPlayer guild={self.mixer.vc.channel.guild} now={self.now}>"