# RT - Server Management 2
import asyncio

import discord
from discord.ext import commands

from core import Cog, RT


FSPARENT = "server-management2"


class ServerManagement2(Cog):
    def __init__(self, bot: RT):
        self.bot: RT = bot

    @commands.command(description="Kick a user", fsparent=FSPARENT)
    @discord.app_commands.describe(target="Target member", reason="Reason")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, target: discord.Member, *, reason: str | None = None):
        await target.kick(reason=reason)
        await ctx.reply(f"👋 Kicked {self.name_and_id(target)}")
        
    @commands.command(description="Ban a user", fsparent=FSPARENT)
    @discord.app_commands.describe(target_ids="Target user ids", reason="Reason")
    @commands.has_permissions(ban_members=True)
    @commands.cooldown(1, 60, commands.BucketType.guild)
    async def ban(self, ctx, target_ids: commands.Greedy[int], *, reason: str | None = None):
        if len(target_ids) > 10:
            raise Cog.BadRequest({"ja": "10人以下までしかできません。", "en": "You can only specify up to 10 people."})
        await asyncio.gather(*(ctx.guild.ban(
            discord.Object(target_id, reason=reason)
            for target_id in target_ids)
        )
        await ctx.reply("\n".join(f"👋 Baned `{target_id}`" for target_id in target_ids))

    @commands.command(
        aliases=("sm", "channel_cooldown", "スローモード", "チャンネルクールダウン"),
        description="Set slowmode", fsparent=FSPARENT
    )
    @discord.app_commands.describe(seconds=(_c_d := "Setting seconds"))
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int):
        await ctx.channel.edit(slowmode=seconds)
        await ctx.reply("Ok")

    Cog.HelpCommand(kick) \
        .merge_description("headline", ja="ユーザーをkickします。") \
        .add_arg("target", "Member", ja="対象とするユーザー", en="Target member") \
        .add_arg("reason", "str", ja="理由", en="reason")

    Cog.HelpCommand(ban) \
        .merge_description("headline", ja="対象のユーザーをbanします。") \
        .add_arg("target_ids", "int", ja="対象とするユーザーID(複数指定可)", en="Target user id(Multiple designations allowed)") \
        .add_arg("reason", "str", ja="理由", en="reason")

    Cog.HelpCommand(slowmode) \
        .merge_description("headline", ja="スローモードを設定します。") \
        .add_arg("seconds", "int", ja="設定する秒数", en=_c_d)
    
    del _c_d


async def setup(bot: RT) -> None:
    await bot.add_cog(ServerManagement2(bot))
