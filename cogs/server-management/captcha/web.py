# RT - OneClick Captcha

import discord

from core import t

from data import URL, NOT_PAID

from .part import CaptchaPart, CaptchaContext


class WebCaptchaPart(CaptchaPart):
    async def on_button_push(self, _: CaptchaContext, interaction: discord.Interaction) -> None:
        assert interaction.guild_id is not None
        if not await self.cog.bot.customers.check(interaction.guild_id):
            await interaction.response.send_message(t(NOT_PAID, interaction), ephemeral=True)
            return

        view = discord.ui.View(timeout=0.0)
        view.add_item(discord.ui.Button(
            label="Go captcha page", url=f"{URL}/captcha/login/{interaction.guild_id}"
        ))
        await interaction.response.send_message(t(dict(
            ja="以下でウェブ認証を行なってください。",
            en="Please perform web authentication below."
        ), interaction), view=view, ephemeral=True)

    async def on_success(self, user_id: int) -> str:
        for guild_id, member in self.cog.queues.keys():
            if member.id == user_id:
                break
        else:
            return t(dict(
                ja="あなたは認証対象ではないようです。",
                en="It appears that you are not eligible for captcha."
            ), user_id)
        return await self.cog.on_success(self.cog.queues[(guild_id, member)], None)