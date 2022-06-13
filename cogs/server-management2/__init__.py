# RT - Server Management 2
import discord
from discord.ext import commands

from core import Cog


FSPARENT = "server-management2"


class ServerManagement(Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command(description="Kick a user", fsparent=FSPARENT)
    @discord.app_commands.describe(target="Target member", reason="Reason")
    async def kick(self, ctx, target: discord.Member, *, reason: str=None):
        await target.kick(reason=reason)
        await ctx.reply(f"👋 Kicked {self.name_and_id(target)}")
        
    Cog.HelpCommand(kick) \
        .merge_description("headline", ja="ユーザーをkickします。") \
        .add_args("target", "Member", ja="対象とするユーザー", en="Target member") \
        .add_args("reason", "str", ja="理由", en="reason")
        

async def setup(bot):
    await bot.add_cog(ServerManagement(bot))
