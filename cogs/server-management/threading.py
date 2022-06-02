# RT - Threading

from __future__ import annotations

from typing import TypeAlias, Literal

from discord.ext import commands
import discord

from core import Cog, RT, t, DatabaseManager, cursor

from data import FORBIDDEN, NO_MORE_SETTING


Mode: TypeAlias = Literal["monitor", "notification"]
class DataManager(DatabaseManager):
    def __init__(self, cog: Threading):
        self.cog = cog
        self.pool = self.cog.bot.pool

    async def prepare_table(self) -> None:
        "テーブルを作ります。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS ThreadingToggleFeatures (
                GuildId BIGINT, ChannelId BIGINT, Mode ENUM('monitor', 'notification')
            );"""
        )

    async def read(self, channel_id: int, mode: Mode, **_) -> bool:
        "スレッドアーカイブ防止の監視のON/OFFを取得します。"
        await cursor.execute(
            "SELECT ChannelId FROM ThreadMonitor LIMIT 1 WHERE ChannelId = %s AND Mode = %s;",
            (channel_id, mode)
        )
        return bool(await cursor.fetchone())

    async def read_monitors(self, guild_id: int, **_) -> set[int]:
        "スレッドアーカイブ防止の監視対象のチャンネルIDの集合を取得します。"
        await cursor.execute(
            "SELECT ChannelId FROM ThreadMonitor WHERE GuildId = %s;",
            (guild_id,)
        )
        return set(map(lambda x: x[0], await cursor.fetchall()))

    MAX_MONITORS = 15

    async def toggle_monitor(self, guild_id: int, channel_id: int) -> None:
        "スレッドのアーカイブ防止の監視のON/OFFの切り替えをします。"
        if len(rows := await self.read_monitors(guild_id, cursor=cursor)) >= self.MAX_MONITORS:
            raise Cog.BadRequest(NO_MORE_SETTING)
        if channel_id in rows:
            await cursor.execute(
                "DELETE FROM ThreadMonitor WHERE ChannelId = %s;",
                (channel_id,)
            )
        else:
            await cursor.execute(
                "INSERT INTO ThreadMonitor VALUES (%s, %s);",
                (guild_id, channel_id)
            )


async def setup(bot: RT) -> None:
    await bot.add_cog(Threading(bot))