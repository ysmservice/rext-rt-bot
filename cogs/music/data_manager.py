# RT Music - Data Manager

from __future__ import annotations

from typing import TYPE_CHECKING

from core import DatabaseManager, cursor

from rtlib.common.cacher import Cacher
from rtlib.common.json import loads, dumps

if TYPE_CHECKING:
    from .__init__ import MusicCog


class DataManager(DatabaseManager):
    def __init__(self, cog: MusicCog):
        self.cog = cog
        self.pool = self.cog.bot.pool
        self.dj_role_caches: Cacher[int, int | None] = self.cog.bot.cachers.acquire(300.0)

    async def prepare_table(self) -> None:
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS DjRole (
                GuildId BIGINT PRIMARY KEY NOT NULL, RoleId BIGINT NOT NULL
            );"""
        )
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS Playlists (
                UserId BIGINT, PlaylistName TEXT,
                Music JSON
            );"""
        )

    async def set_dj_role(self, guild_id: int, role_id: int | None) -> None:
        "DJロールを設定します。"
        if role_id is None:
            await cursor.execute(
                "DELETE FROM DjRole WHERE RoleId = %s;",
                (role_id,)
            )
        else:
            await cursor.execute(
                """INSERT INTO DjRole VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE RoleId = %s;""",
                (guild_id, role_id, role_id)
            )
        self.dj_role_caches[guild_id] = role_id

    async def get_dj_role_id(self, guild_id: int) -> int | None:
        "DJロールを取得します。"
        if guild_id not in self.dj_role_caches:
            await cursor.execute(
                "SELECT RoleId FROM DjRole WHERE GuildId = %s LIMIT 1;",
                (guild_id,)
            )
            self.dj_role_caches[guild_id] = row[0] \
                if (row := await cursor.fetchone()) else None
        return self.dj_role_caches[guild_id]