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
    async def kick(self, ctx, target: discord.Member, *, reason: str = None):
        await target.kick(reason=reason)
        await ctx.reply(f"👋 Kicked {self.name_and_id(target)}")

    Cog.HelpCommand(kick) \
        .merge_description("headline", ja="ユーザーをkickします。") \
        .add_arg("target", "Member", ja="対象とするユーザー", en="Target member") \
        .add_arg("reason", "str", ja="理由", en="reason")


async def setup(bot: RT) -> None:
    await bot.add_cog(ServerManagement2(bot))
