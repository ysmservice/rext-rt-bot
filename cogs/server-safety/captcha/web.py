# RT - OneClick Captcha

import discord

from core import t

from data import HOST_PORT

from .part import CaptchaPart, CaptchaContext


class WebCaptchaPart(CaptchaPart):
    async def on_button_push(self, _: CaptchaContext, interaction: discord.Interaction) -> None:
        view = discord.ui.View(timeout=0.0)
        view.add_item(discord.ui.Button(
            label="Go captcha page",
            url=f"https://{HOST_PORT}/captcha"
        ))
        await interaction.response.send_message(t(dict(
            ja="以下でウェブ認証を行なってください。",
            en="Please perform web authentication below."
        ), interaction), view=view)

    async def on_success(self, user_id: int) -> str:
        for member in self.cog.queues.keys():
            if member.id == user_id:
                break
        else:
            return t(dict(
                ja="あなたは認証対象ではないようです。",
                en="It appears that you are not eligible for captcha."
            ), user_id)
        return await self.cog.on_success(self.cog.queues[member], None)