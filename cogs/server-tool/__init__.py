# RT - Server Tool

from discord.ext import commands
import discord

from core import Cog, RT, t


FSPARENT = "server-tool"


class ServerTool(Cog):
    def __init__(self, bot: RT):
        self.bot = bot

    @commands.command(
        aliases=("invs", "招待ランキング"), fsparent=FSPARENT,
        description="Invitation ranking is displayed."
    )
    async def invites(self, ctx: commands.Context):
        assert ctx.guild is not None
        await ctx.reply(embed=Cog.Embed(
            title=t(dict(
                ja="{guild_name}の招待ランキング",
                en="Invitation ranking of {guild_name}"
            ), ctx, guild_name=ctx.guild.name), description='\n'.join(
                f"{a}：`{c}`" for a, c in sorted((
                    (f"{i.inviter.mention}({i.code})", i.uses or 0)
                    for i in await ctx.guild.invites()
                    if i.inviter is not None and i.uses
                ), reverse=True, key=lambda x: x[1])
            )
        ))

    (Cog.HelpCommand(invites)
        .merge_headline(ja="招待ランキング")
        .set_description(ja="招待ランキングを表示します。", en=invites.description))


async def setup(bot: RT) -> None:
    await bot.add_cog(ServerTool(bot))