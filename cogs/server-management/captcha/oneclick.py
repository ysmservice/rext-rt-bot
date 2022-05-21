# RT - OneClick Captcha

import discord

from .part import CaptchaPart, CaptchaContext


class OneClickCaptchaPart(CaptchaPart):
    async def on_button_push(self, ctx: CaptchaContext, interaction: discord.Interaction) -> None:
        await self.cog.on_success(ctx, interaction, "send")