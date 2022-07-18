# RT - Customer Pool

from __future__ import annotations

from typing import TYPE_CHECKING

from rtlib.common.cacher import Cacher
from rtlib.common.reply_error import BadRequest

from data import NOT_PAID

if TYPE_CHECKING:
    from .types_ import Text
    from .bot import RT


__all__ = ("CustomerPool", "Plan")


class Plan:
    "数制限の数を取得するためのクラスです。"

    def __init__(self, pool: CustomerPool, free: int, customer: int):
        self.pool, self.free, self.customer = pool, free, customer

    async def calculate(self, guild_id: int) -> int:
        "指定されたサーバーに相応しい数制限の数を返します。"
        return self.customer if await self.pool.check(guild_id) else self.free


class CustomerPool:
    "製品版購入者の情報を取得したりするためのクラスです。"

    def __init__(self, bot: RT):
        self.bot = bot
        self.caches: Cacher[int, bool] = self.bot.cachers.acquire(900.0)
        self.bot.loop.create_task(self.prepare_table(), name="CreateCustomersTable")

    async def prepare_table(self) -> None:
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    """CREATE TABLE IF NOT EXISTS Customers (
                        GuildId BIGINT PRIMARY KEY NOT NULL,
                        UserId BIGINT, Deadline DOUBLE
                    );"""
                )

    async def check(self, guild_id: int) -> bool:
        "指定されたサーバーが製品版を所有しているかどうかを調べます。"
        if guild_id not in self.caches:
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT GuildId FROM Customers WHERE GuildId = %s LIMIT 1;",
                        (guild_id,)
                    )
                    self.caches[guild_id] = bool(await cursor.fetchone())
        return self.caches[guild_id]

    async def assert_(self, guild_id: int, resopnse_text: Text = NOT_PAID) -> None:
        "指定されたサーバーが製品版適用済みではない場合は`rtlib.common.reply_error.ReplyError`を発生させます。"
        if not await self.bot.customers.check(guild_id):
            raise BadRequest(resopnse_text)

    def acquire(self, free: int, customer: int) -> Plan:
        "プランを作ります。"
        return Plan(self, free, customer)

    def remove_customer_cache(self, guild_id: int) -> None:
        "指定されたサーバーIDのキャッシュを削除します。"
        if guild_id in self.caches:
            del self.caches[guild_id]