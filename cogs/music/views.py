# RT Music - Views

from typing import TypeAlias, Any
from collections.abc import Callable, Coroutine

import discord

from core import Cog, t
from core.utils import concat_text

from rtutil.views import TimeoutView

from .utils import can_control


ConfirmCoroutine: TypeAlias = Coroutine[Any, Any, str]
class ConfirmView(TimeoutView):
    "確認ボタンを実装したViewです。"

    def __init__(
        self, coroutine: ConfirmCoroutine, required: int,
        *args: Any, **kwargs: Any
    ):
        kwargs.setdefault("timeout", 180.0)
        super().__init__(*args, **kwargs)
        self.coroutine, self.required, self.ok = coroutine, required, set()

    @discord.ui.button(label="Okay", emoji="✅")
    async def confirm(self, interaction: discord.Interaction, _):
        self.ok.add(interaction.user)
        if len(self.ok) >= self.required:
            await interaction.response.send_message(t(dict(
                ja="みんながOKしたので実効が決まりました。",
                en="Everyone said yes, so we decided to do the action."
            ), interaction))
            await interaction.edit_original_message(content=await self.coroutine)
        else:
            await interaction.response.send_message("Ok", ephemeral=True)
        self.set_message(interaction)

    @classmethod
    async def process(
        cls, ctx: Cog.Context, content: dict[str, str],
        dj_role_id: int | None, coroutine: ConfirmCoroutine
    ) -> None:
        "渡されたコルーチンを実行します。また、他の人への確認が必要無場合は確認を行います。"
        assert isinstance(ctx.author, discord.Member) and ctx.author.voice is not None \
            and ctx.author.voice.channel is not None
        if can_control(ctx.author, dj_role_id):
            await ctx.reply(await coroutine)
        else:
            view = cls(coroutine, len(ctx.author.voice.channel.members))
            view.set_message(ctx, await ctx.reply(t(concat_text(content, {
                "ja": "あなたはDJロールまたは権限を持っていないためこの操作を実行することができません。"
                    "\nそこで、みんなに聞いてみたいと思います。",
                "en": "You do not have the DJ role or authority to perform this operation."
                    "\nSo I would like to ask everyone."
            }), ctx), view=view))