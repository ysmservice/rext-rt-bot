# RT - Role Panel

from discord.ext import commands
import discord

from core import Cog, RT, t

from rtutil.panel import extract_emojis
from rtutil.utils import artificially_send

from .__init__ import FSPARENT


class RolePanel(Cog):
    def __init__(self, bot: RT):
        self.bot = bot

    @commands.command(
        aliases=("rp", "役職パネル", "ロールパネル", "やぱ", "ろぱ"), fsparent=FSPARENT
        description="Create a role panel."
    )
    async def role(
        self, ctx: commands.Context, max_: int = -1, min = -1,
        title: str = "Role Panel", *, content: str
    ):
        assert isinstance(ctx.channel, discord.TextChannel | discord.Thread)
        emojis = extract_emojis(content)
        await artificially_send(ctx.channel, ctx.author, embed=discord.Embed(
            title=title, description="\n".join(
                f"{emoji} {(await commands.RoleConverter().convert(ctx, value)).mention}"
                for emoji, value in emojis.items()
            ), color=ctx.author.color
        ))
        if ctx.interaction is not None:
            await ctx.interaction.response.send_message("Ok", ephemeral=True)


async def setup(bot: RT) -> None:
    await bot.add_cog(RolePanel(bot))