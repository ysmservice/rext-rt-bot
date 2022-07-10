# RT - Customer Pool

from __future__ import annotations

from typing import TYPE_CHECKING

from rtlib.common.cacher import Cacher

if TYPE_CHECKING:
    from .bot import RT


__all__ = ("CustomerPool",)


class CustomerPool:
    "製品版購入者の情報を取得したりするためのクラスです。"

    def __init__(self, bot: RT):
        self.bot = bot
        self.caches: Cacher[int, bool] = self.bot.cachers.acquire(900.0)

    async def check(self, user_id: int) -> bool:
        "指定されたユーザーが製品版所有者かどうかを調べます。"
        if user_id not in self.caches:
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "SELECT UserId FROM Customers WHERE UserId = %s LIMIT 1;",
                        (user_id,)
                    )
                    self.caches[user_id] = bool(await cursor.fetchone())
        return self.caches[user_id]