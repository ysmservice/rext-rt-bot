# RT - Server Management 2

import discord
from discord.ext import commands

from core import Cog, RT


FSPARENT = "server-management2"


class ServerManagement2(Cog):
    def __init__(self, bot: RT):
        self.bot = bot

    @commands.command(description="Kick a user", fsparent=FSPARENT)
    @discord.app_commands.describe(target="Target member", reason="Reason")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, target: discord.Member, *, reason: str = None):
        await target.kick(reason=reason)
        await ctx.reply(f"👋 Kicked {self.name_and_id(target)}")
        
    @commands.command(description="Ban a user", fsparent=FSPARENT)
    @discord.app_commands.describe(target_id="Target user id", reason="Reason")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, target_id: int, *, reason: str = None):
        await ctx.guild.ban(discord.Object(target_id), reason=reason)
        await ctx.reply(f"👋 Baned `{target_id}`")

    Cog.HelpCommand(kick) \
        .merge_description("headline", ja="ユーザーをkickします。") \
        .add_arg("target", "Member", ja="対象とするユーザー", en="Target member") \
        .add_arg("reason", "str", ja="理由", en="reason")

    Cog.HelpCommand(ban) \
        .merge_description("headline", ja="対象のユーザーをbanします。") \
        .add_arg("target_id", "int", ja="対象とするユーザーID", en="Target user id") \
        .add_arg("reason", "str", ja="理由", en="reason")


async def setup(bot: RT) -> None:
    await bot.add_cog(ServerManagement2(bot))
