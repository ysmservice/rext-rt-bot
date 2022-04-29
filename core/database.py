# RT - Data Manager

from typing import TypeVar

from inspect import iscoroutinefunction, getsource, getfile
from warnings import filterwarnings
from functools import wraps

from aiomysql import Pool, Cursor


filterwarnings('ignore', module=r"aiomysql")
__all__ = ("DatabaseManager", "cursor")
cursor: Cursor
cursor = None # type: ignore


CaT = TypeVar("CaT")
class DatabaseManager:

    pool: Pool

    def __init_subclass__(cls):
        for key, value in list(cls.__dict__.items()):
            if iscoroutinefunction(value) and not getattr(value, "__dm_ignore__", False):
                # `cursor`の引数を増設する。
                l = {}
                source = getsource(value).replace("self",  "self, cursor", 1)
                if_count = int(len(source[:source.find("d")]) / 4) - 1
                source = "{}{}".format(
                    "\n" * (value.__code__.co_firstlineno - if_count - 1), "\n".join((
                    "\n".join(f"{'    '*i}if True:" for i in range(if_count)), source
                )))
                exec(compile(source, getfile(value), "exec"), value.__globals__, l)
                # 新しい関数を作る。
                @wraps(l[key])
                async def _new(
                    self: DatabaseManager, *args, __dm_func__=l[key], **kwargs
                ):
                    if "cursor" in kwargs:
                        return await __dm_func__(self, kwargs.pop("cursor"), *args, **kwargs)
                    else:
                        async with self.pool.acquire() as conn:
                            async with conn.cursor() as cursor:
                                return await __dm_func__(self, cursor, *args, **kwargs)
                setattr(cls, key, _new)

    @staticmethod
    def ignore(func: CaT) -> CaT:
        setattr(func, "__dm_ignore__", True)
        return func