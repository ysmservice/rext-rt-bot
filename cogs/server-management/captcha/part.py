# RT Captcha - Part

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, TypeAlias, Literal, Any

from types import SimpleNamespace
from time import time

import discord

from core import t

from rtlib.common.cacher import Cacher

if TYPE_CHECKING:
    from core.rtevent import EventContext

    from .__init__ import Captcha, RowData


FAILED_CODE = {"ja": "コードが違います。", "en": "It is a wrong code."}
Mode: TypeAlias = Literal["image", "word", "web", "oneclick"]
RowData = NamedTuple("Row", (
    ("guild_id", "int"), ("role_id", int), ("mode", Mode),
    ("deadline", float), ("kick", bool), ("extras", dict[str, Any])
))


class CaptchaContext(SimpleNamespace):
    "認証の情報を格納するためのクラスです。"

    data: RowData
    part: CaptchaPart
    member: discord.Member
    event_context: EventContext
    success: bool = False


class CaptchaView(discord.ui.View):
    def __init__(self, cog: Captcha, *args, **kwargs):
        self.cog = cog
        self._cache: Cacher[tuple[int, int], tuple[float, int]] = \
            self.cog.bot.cachers.acquire(1800.0)
        kwargs.setdefault("timeout", None)
        super().__init__(*args, **kwargs)

    @discord.ui.button(label="Start captcha", custom_id="captcha.start", emoji="🔎")
    async def start(self, interaction: discord.Interaction, _):
        assert interaction.message is not None and isinstance(interaction.user, discord.Member) \
            and interaction.guild_id is not None
        if (interaction.guild_id, interaction.user) in self.cog.queues:
            # やればやるほど待機しなければならないようにした。
            now, key = time(), (interaction.guild_id, interaction.user.id)
            if key not in self._cache:
                self._cache[key] = (now, 0)
            if now < self._cache[key][0]:
                await interaction.response.send_message(t(dict(
                    ja="クールダウン中です。\n{after:.2f}秒後にお試しください。",
                    en="It is in cooldown.\nPlease try again after {after:.2f} seconds."
                ), interaction, after=self._cache[key][0] - now), ephemeral=True)
            else:
                count = self._cache[key][1] + 1
                if count == 13:
                    self._cache.merge_deadline(key)
                else:
                    self._cache[key] = (
                        now + count * 10 * count, count
                    )

                await self.cog.queues[(interaction.guild_id, interaction.user)] \
                    .part.on_button_push(
                        self.cog.queues[(interaction.guild_id, interaction.user)],
                        interaction
                    )
        else:
            await interaction.response.send_message(t(dict(
                ja="あなたは認証対象ではありません。\n考えられる原因：放置した, サーバーの認証が解除された, 既にロールを所有している",
                en="You are not eligible for captcha.\nPossible causes: You are neglected, The setting is deactivated, Already own the role"
            ), interaction), ephemeral=True)


class CaptchaPart:
    def __init__(self, cog: Captcha):
        self.cog = cog

    async def on_queue_remove(self, ctx: CaptchaContext) -> None:
        "メンバーが消えた際に呼ばれます。"

    async def on_button_push(self, ctx: CaptchaContext, interaction: discord.Interaction) -> None:
        "ボタンが押された際に呼び出されます。"
