# RT - RTA

from __future__ import annotations

from typing import Optional

from discord.ext import commands, tasks
from discord import app_commands
import discord

from datetime import datetime, timezone
from time import time

from aiomysql import Pool

from rtlib import RT, DatabaseManager, Cog, cursor


class DataManager(DatabaseManager):

    TABLES = ("rta",)

    def __init__(self, bot: RT):
        self.pool: Pool = bot.mysql.pool
        self.bot = bot
        self.bot.loop.create_task(self._prepare_table())

    async def _get(self, guild_id: int):
        await cursor.execute(
            f"SELECT channel FROM {self.TABLES[0]} WHERE guild = %s;",
            (guild_id,)
        )
        if row := await cursor.fetchone():
            return self.bot.get_channel(row[0])

    async def get_channel(
        self, guild_id: int
    ) -> Optional[discord.TextChannel]:
        return await self._get(guild_id, cursor)

    async def _prepare_table(self):
        # テーブルを用意します。
        await cursor.execute(
            f"""CREATE TABLE IF NOT EXISTS {self.TABLES[0]} (
                guild BIGINT PRIMARY KEY NOT NULL, channel BIGINT
            );"""
        )

    async def set_rta(
        self, guild_id: int, channel_id: int
    ) -> bool:
        if await self._get(guild_id, cursor) is None:
            await cursor.execute(
                f"INSERT INTO {self.TABLES[0]} VALUES (%s, %s);",
                (guild_id, channel_id)
            )
            return True
        else:
            await cursor.execute(
                f"DELETE FROM {self.TABLES[0]} WHERE guild = %s;", (guild_id,)
            )
            return False


class RTA(commands.Cog):
    def __init__(self, bot: RT):
        self.db, self.bot = DataManager(bot), bot
        self.sended_remover.start()
        self.sended: dict[str, float] = bot.acquire(60)

    @commands.group(description="即抜けRTA機能")
    @commands.has_guild_permissions(kick_members=True)
    async def rta(self, ctx):
        """!lang ja
        -------
        即抜けRTA通知用のコマンドです。
        
        Aliases
        -------
        RTA, あーるてぃーえー, 即抜け, rta_notification, rta_notice
        
        !lang en
        --------
        This is the leaving RTA notification command.
        Aliases
        -------
        RTA, rta_notification, rta_notice"""
        if ctx.invoked_subcommand is None:
            await ctx.reply("コマンドの使いかたが間違っています。")

    @rta.command(aliases=["set", "設定"])
    @app_commands.describe(channel="channel's name")
    async def setup(self, ctx, channel: Optional[discord.TextChannel] = None):
        if await self.db.set_rta(ctx.guild.id, (channel := (channel or ctx.channel)).id):
            await ctx.reply(
                embed=discord.Embed(
                    title="success",
                    description=f"rta通知チャンネルを{channel.mention}にしました。",
                    color=self.bot.Colors.normal
                )
            )
        else:
            await ctx.reply(
                embed=discord.Embed(
                    title="success",
                    description=f"{channel.mention}のRTA通知を解除しました",
                    color=self.bot.Colors.normal
                )
            )
            
    Cog.HelpCommand(rta) \
        .set_description(ja="即抜けRTA通知用のコマンドです", en="Set channel which recording the leaving RTA.") \
        .set_extra("Notes", ja="もう一度このコマンドを実行するとRTA設定をOffにできます。",
                   en="Run this command again to turn off the RTA setting.")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if f"{member.guild.id}-{member.id}" in self.sended:
            return # もし既にRTAメッセージを送信しているならやめる。

        joined_after = datetime.now(timezone.utc) - member.joined_at
        if joined_after.days == 0 and joined_after.seconds < 60:
            if (channel := await self.db.get_channel(member.guild.id)) is not None:
                await channel.send(embed=discord.Embed(
                    title="即抜けRTA",
                    description=f"{member}が{round(joined_after.seconds, 6)}秒で抜けちゃった。。。",
                    color=self.bot.Colors.unknown
                ))
                self.sended[f"{member.guild.id}-{member.id}"] = time()

    async def cog_unload(self):
        self.sended_remover.cancel()


async def setup(bot):
    await bot.add_cog(RTA(bot))
