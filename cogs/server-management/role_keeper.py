# RT - Role Keeper

from __future__ import annotations

from collections.abc import Sequence

from time import time

from discord.ext import commands
import discord

from core import Cog, RT, t, DatabaseManager, cursor

from rtlib.common.json import dumps, loads
from rtlib.common.cacher import Cacher

from data import ROLE_NOTFOUND, FORBIDDEN

from .__init__ import FSPARENT


class DataManager(DatabaseManager):
    def __init__(self, cog: RoleKeeper):
        self.cog = cog
        self.pool = self.cog.bot.pool
        self.caches: Cacher[int, bool] = self.cog.bot.cachers.acquire(180.0)

    async def prepare_table(self) -> None:
        "テーブルを作ります。"
        await cursor.execute(
            "CREATE TABLE IF NOT EXISTS RoleKeeper (GuildId BIGINT);"
        )
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS RoleKeeperCache (
                GuildId BIGINT, UserId BIGINT, Roles JSON, RegisteredAt FLOAT
            );"""
        )

    async def is_on(self, guild_id: int, **_) -> bool:
        "ONかどうかを調べます。"
        if guild_id not in self.caches:
            await cursor.execute(
                "SELECT * FROM RoleKeeper WHERE GuildId = %s LIMIT 1;",
                (guild_id,)
            )
            self.caches[guild_id] = bool(await cursor.fetchone())
        return self.caches[guild_id]

    async def toggle(self, guild_id: int) -> None:
        "ロールキーパーの設定の無効/有効を切り替えます。"
        if await self.is_on(guild_id, cursor=cursor):
            await cursor.execute("DELETE FROM RoleKeeper WHERE GuildId = %s;", (guild_id,))
            await cursor.execute(
                "DELETE FROM RoleKeeperCache WHERE GuildId = %s;",
                (guild_id,)
            )
            self.caches[guild_id] = False
        else:
            await cursor.execute("INSERT INTO RoleKeeper VALUES (%s);", (guild_id,))
            self.caches[guild_id] = True

    async def get_cache(self, guild_id: int, user_id: int, delete: bool = True, **_) \
            -> Sequence[int] | None:
        "ロールキーパーのロールのキャッシュを取得します。"
        await cursor.execute(
            "SELECT Roles FROM RoleKeeperCache WHERE GuildId = %s AND UserId = %s LIMIT 1;",
            (guild_id, user_id)
        )
        if row := await cursor.fetchone():
            if delete:
                await cursor.execute(
                    "DELETE FROM RoleKeeperCache WHERE GuildId = %s AND UserId = %s;",
                    (guild_id, user_id)
                )
            return loads(row[0])

    async def set_cache(self, guild_id: int, user_id: int, roles: Sequence[int]) -> None:
        "キャッシュを設定します。"
        if await self.get_cache(guild_id, user_id, delete=False, cursor=cursor):
            await cursor.execute(
                """UPDATE RoleKeeperCache SET Roles = %s
                    WHERE GuildId = %s AND UserId = %s AND RegisteredAt = %s;""",
                (dumps(roles), guild_id, user_id, time())
            )
        else:
            await cursor.execute(
                "INSERT INTO RoleKeeperCache VALUES (%s, %s, %s, %s);",
                (guild_id, user_id, dumps(roles), time())
            )

    CACHE_DEADLINE = 31536000

    async def clean(self) -> None:
        await self.clean_data(cursor, "RoleKeeper", "GuildId")
        now = time()
        async for row in self.fetchstep(cursor, "SELECT * FROM RoleKeeperCache;"):
            if now - row[-1] > self.CACHE_DEADLINE:
                await cursor.execute(
                    """DELETE FROM RoleKeeperCache
                        WHERE GuildId = %s AND UserId = %s AND RegisteredAt = %s;""",
                    row[:2] + row[-1:]
                )


class RoleKeeperRoleAddEventContext(Cog.EventContext):
    "ロールキーパーのロール付与のイベントコンテキストです。"

    roles: list[discord.Role]
    member: discord.Member


class RoleKeeper(Cog):
    "ロールキーパーのコグです。"

    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.command(
        aliases=("rk", "ロールキーパー", "役職管理人"), fsparent=FSPARENT,
        description="Even if a user leaves the server once, the same role is granted when the user joins again."
    )
    @commands.has_guild_permissions(manage_roles=True)
    @commands.cooldown(1, 30, commands.BucketType.guild)
    async def role_keeper(self, ctx: commands.Context):
        assert ctx.guild is not None
        async with ctx.typing():
            await self.data.toggle(ctx.guild.id)
        await ctx.reply("Ok")

    (Cog.HelpCommand(role_keeper)
        .merge_headline(ja="ユーザーが一度サーバーから退出しても、また参加した時に同じロールを付与する。")
        .set_description(
            ja="ユーザーが一度サーバーから退出しても、また参加した時に同じロールを付与する機能です。",
            en=role_keeper.description
        )
        .set_extra("Notes",
            ja="ロールのデータは一年保持されます。", en="Data for roles is retained for one year."))

    @commands.Cog.listener()
    async def on_member_remove_cooldown(self, member: discord.Member):
        if await self.data.is_on(member.guild.id):
            await self.data.set_cache(member.guild.id, member.id, [
                role.id for role in member.roles if not role.is_default()
            ])

    @commands.Cog.listener()
    async def on_member_join_cooldown(self, member: discord.Member):
        if await self.data.is_on(member.guild.id) \
                and (roles := await self.data.get_cache(member.guild.id, member.id)) \
                    is not None:
            roles = [
                member.guild.get_role(role_id)
                for role_id in roles
                if member.get_role(role_id) is None
            ]
            detail = ""
            if any(role is None for role in roles):
                detail = ROLE_NOTFOUND
            else:
                try:
                    await member.add_roles(*roles, reason=t(dict( # type: ignore
                        ja="ロールキーパーのロール付与", en="Role Keeper's Role Added"
                    ), member.guild))
                except discord.Forbidden:
                    detail = FORBIDDEN
            self.bot.rtevent.dispatch("on_role_keeper_role_add", RoleKeeperRoleAddEventContext(
                self.bot, member.guild, "ERROR" if detail else "SUCCESS",
                {"ja": "ロールキーパーのロール付与", "en": "Role Keeper Role Add"},
                detail, self.role_keeper, roles=roles, member=member
            ))


async def setup(bot: RT) -> None:
    await bot.add_cog(RoleKeeper(bot))