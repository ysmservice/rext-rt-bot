# RT Captcha - Part

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, TypeAlias, Literal, Any

from types import SimpleNamespace

import discord

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
        kwargs.setdefault("timeout", None)
        super().__init__(*args, **kwargs)

    @discord.ui.button(custom_id="captcha.start", emoji="🔎")
    async def start(self, interaction: discord.Interaction, _):
        assert interaction.message == "" and isinstance(interaction.user, discord.Member)
        self.cog.queues[interaction.user] = CaptchaContext(member=interaction.user)
        await self.cog.get_part(interaction.message.content).on_button_push(
            self.cog.queues[interaction.user], interaction
        )


class CaptchaPart:
    def __init__(self, cog: Captcha):
        self.cog = cog

    async def on_queue_remove(self, ctx: CaptchaContext) -> None:
        "メンバーが消えた際に呼ばれます。"

    async def on_button_push(self, ctx: CaptchaContext, interaction: discord.Interaction) -> None:
        "ボタンが押された際に呼び出されます。"
