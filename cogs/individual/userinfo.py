# RT - Userinfo
from discord.ext import commands
from discord import app_commands, Member

from core import Cog, t


class Userinfo(Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(description="search user")
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
            name=t({"ja": "Discord登録日時", "en": "Discord register time"}, ctx),
            value=user.created_at
        )
        embed.add_field(
            name=t({"ja": "アバターURL", "en": "Avatar url"}, ctx),
            value=getattr(user.avatar, "url", "null"),
            inline=False
        )
        embed.set_thumbnail(url=user.avatar.url)
        embeds.append(embed)
        member = await ctx.bot.search_member(ctx.guild, user.id)
        if member is not None:
            embed = Cog.Embed(
                title=t({"en": "At this server information", "ja": "このサーバーの情報"}, ctx),
                description=", ".join(role.mention for role in member.roles)
            )
            embed.add_field(
                name=t({"en": "Show name", "ja": "表示名"}, ctx),
                value=member.nick if member.nick is not None else member.name
            )
            embed.add_field(
                name=t({"en": "Joined at", "ja": "参加日時"}, ctx),
                value=member.joined_at
            )
            embeds.append(embed)
        await ctx.send(embeds=embeds)
        
    Cog.HelpCommand(userinfo) \
        .set_headline(ja="ユーザーを検索します。") \
        .add_arg("userid", "str", "Optional",
                 ja="ユーザーID", en="User ID") \
        .set_description(ja="ユーザーを検索します", en="Search user")
 

async def setup(bot):
    await bot.add_cog(Userinfo(bot))
