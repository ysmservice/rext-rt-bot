# RT - RTA

from __future__ import annotations

from typing import Optional

from discord.ext import commands
from discord import app_commands
import discord

from datetime import datetime, timezone
from time import time

from rtlib.types_ import Channel
from rtlib.database import DatabaseManager, cursor
from rtlib.cacher import Cacher
from rtlib import RT, Cog, t


class DataManager(DatabaseManager):

    TABLES = ("rta",)

    def __init__(self, bot: RT):
        self.pool, self.bot = bot.pool, bot

    async def get(self, guild_id: int, **_) -> Optional[Channel]:
        "RTAの設定を読み込みます。"
        await cursor.execute(
            "SELECT channel FROM {} WHERE guild = %s;".format(self.TABLES[0]),
            (guild_id,)
        )
        if row := await cursor.fetchone():
            return self.bot.get_channel(row[0])

    async def prepare_table(self):
        "テーブルを用意します。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS {} (
                guild BIGINT PRIMARY KEY NOT NULL, channel BIGINT
            );""".format(self.TABLES[0])
        )

    async def set(self, guild_id: int, channel_id: int) -> bool:
        "RTAを設定します。"
        if await self.get(guild_id, cursor=cursor) is None:
            await cursor.execute(
                "INSERT INTO {} VALUES (%s, %s);".format(self.TABLES[0]),
                (guild_id, channel_id)
            )
            return True
        else:
            await cursor.execute(
                "DELETE FROM {} WHERE guild = %s;".format(self.TABLES[0]),
                (guild_id,)
            )
            return False


IMMEDIATE_EXIT = dict(ja="即抜けRTA", en="")
class RTA(Cog):
    def __init__(self, bot: RT):
        self.db, self.bot = DataManager(bot), bot
        self.sended: Cacher[str, float] = bot.cachers.acquire(60)

    async def cog_load(self):
        await self.db.prepare_table()

    @commands.command(description="Setup a rta")
    @app_commands.describe(channel="Notify target channel")
    async def rta(self, ctx, channel: Optional[discord.TextChannel] = None):
        if await self.db.set(ctx.guild.id, (channel := (channel or ctx.channel)).id):
            assert isinstance(channel, discord.TextChannel), t(dict(
                ja="テキストチャンネルでなければいけません。",
                en="It must be a text channel."
            ), ctx)
            await ctx.reply(t(dict(
                ja="即抜けRTA通知チャンネルを{mention}にしました。",
                en="Immediate Exit RTA Notification Channel to {mention}."
            ), ctx, mention=channel.mention))
        else:
            await ctx.reply(t(dict(
                ja="RTA通知を解除しました。", en="RTA notifications have been unset."
            ), ctx))
            
    Cog.HelpCommand(rta) \
        .set_description(ja="即抜けRTA通知用のコマンドです", en="Set channel which recording the leaving RTA.") \
        .set_extra(
            "Notes", ja="もう一度このコマンドを実行するとRTA設定をOffにできます。",
            en="Run this command again to turn off the RTA setting."
        ) \
        .add_arg(
            "channel", "Channel", "Optional", ja="""対象のチャンネルです。
            入力しなかった場合はコマンドを実行したチャンネルとなります。""",
            en="""Target channel.
            If not entered, it is the channel where the command was executed."""
        ) \
        .update_headline(ja="rta機能を設定します")

    @Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        # もし既にRTAメッセージを送信しているまたは参加日が不明の場合はやめる。
        if f"{member.guild.id}-{member.id}" in self.sended or member.joined_at is None:
            return

        joined_after = datetime.now(timezone.utc) - member.joined_at
        if joined_after.days == 0 and joined_after.seconds < 60:
            if (channel := await self.db.get(member.guild.id)) is not None:
                if isinstance(channel, discord.TextChannel):
                    await channel.send(embed=Cog.Embed(
                        title=t(IMMEDIATE_EXIT, member.guild),
                        description=t(dict(
                            ja="{member}が{seconds}秒で抜けちゃった。。。",
                            en="{member} left in {seconds}s."
                        ), member.guild, member=member,
                        seconds=round(joined_after.seconds, 6))
                    ))
                    self.sended[f"{member.guild.id}-{member.id}"] = time()
                else:
                    ... # TODO: RTの処理ログにエラーを流すようにする。


async def setup(bot):
    await bot.add_cog(RTA(bot))
