# RT - Word captcha

from typing import TypedDict, Literal

import discord

from core import t

from .part import CaptchaPart, CaptchaContext, RowData


class WordExtras(TypedDict):
    "WordRowDataに必要な型です。"

    word: str
    mode: Literal["partial", "full"]


class WordRowData(RowData):
    "WordCaptchaContextに必要な型です。"

    extras: WordExtras


class WordCaptchaContext(CaptchaContext):
    "合言葉認証用に追加で型付けしたCaptchaContextです。"

    data: WordRowData


class WordInputModal(discord.ui.Modal):
    "合言葉を入力するためのモーダルです。"

    word = discord.ui.TextInput(label="Word")

    def __init__(self, ctx: WordCaptchaContext, *args, **kwargs):
        self.ctx = ctx
        super().__init__(*args, **kwargs)

    async def on_submit(self, interaction: discord.Interaction):
        if (
            self.ctx.data.extras["mode"] == "full"
            and self.ctx.data.extras["word"] == str(self.word)
        ) or (
            self.ctx.data.extras["mode"] == "partial"
            and self.ctx.data.extras["word"] in str(self.word)
        ):
            await self.ctx.part.cog.on_success(self.ctx, interaction, "send")
        else:
            await interaction.response.send_message(t(dict(
                ja="合言葉が違います。", en="The password is different."
            ), interaction), ephemeral=True)


class WordCaptchaPart(CaptchaPart):
    async def on_button_push(
        self, ctx: WordCaptchaContext, interaction: discord.Interaction
    ) -> None:
        await interaction.response.send_modal(WordInputModal(ctx, title=t(dict(
            ja="合言葉を入力してください。", en="Please enter your password."
        ), interaction)))