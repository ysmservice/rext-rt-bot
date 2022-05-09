# RT - Userinfo
from discord.ext import commands
from discord import app_commands, Member

from core import Cog, t


class Userinfo(Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command()
    @app_commands.describe(userid="user id")
    async def userinfo(self, ctx, *, userid: int=None):
        user = await self.bot.search_user(userid if userid is not None else ctx.author.id)
        if user.public_flags.hypesquad_bravery:
            hypesquad = "<:HypeSquad_Bravery:876337861572579350>"
        elif user.public_flags.hypesquad_brilliance:
            hypesquad = "<:HypeSquad_Brilliance:876337861643882506>"
        elif user.public_flags.hypesquad_balance:
            hypesquad = "<:HypeSquad_Balance:876337714679676968>"
        else:
            hypesquad = ""
        embeds = []
        embed = Cog.Embed(
            title=user,
            description=hypesquad
        )
        embed.add_field(
            name="ID",
            value=user.id
        )
        embed.add_field(
            name="Discord登録日時",
            value=user.created_at
        )
        embed.add_field(
            name="アバターURL",
            value=getattr(user.avatar, "url", "null"),
            inline=False
        )
        embeds.append(embed)
        if isinstance(ctx.author, Member):
            embed = Cog.Embed(
                title=t({"en": "At this server information", "ja": "このサーバーの情報"}, ctx),
                description=", ".join(role.mention for role in ctx.guild.roles)
            )
            embed.add_field(
                name=t({"en": "Show name", "ja": "表示名"}, ctx),
                value=ctx.author.nick
            )
            embed.add_field(
                name=t({"en": "Joined at", "ja": "参加日時"}, ctx),
                value=ctx.joined_at
            )
            embeds.append(embed)
        await ctx.send(embeds=embeds)
 

async def setup(bot):
    await bot.add_cog(Userinfo(bot))
