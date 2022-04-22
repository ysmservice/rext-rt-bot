# RT - RT Event

from __future__ import annotations

from typing import TypeAlias, Optional, Any, cast
from collections.abc import Callable, Coroutine, Sequence

from asyncio import create_task
from inspect import iscoroutinefunction
from collections import defaultdict
from functools import wraps

from ujson import loads, dumps

from .utils import make_error_message
from .log import Feature, Target
from .general import Cog, RT


__all__ = ("EventContext", "OnErrorContext", "RTEvent")


class EventContext:
    "イベントデータを格納する`Context`のベースです。"

    feature: Feature = ("Unknown", "...")

    def __init__(
        self, target: Optional[Target] = None, status: str = "SUCCESS",
        detail: str = "...", log: bool = True, **kwargs
    ):
        self.keys = []
        for key, value in kwargs.items():
            setattr(self, key, value)
            self.keys.append(key)
        self.log, self.status, self.detail, self.target = log, status, detail, target

    def to_dict(self) -> dict[str, Any]:
        "格納されているデータを辞書にします。"
        return {
            key: value for key, value in self.__dict__.items()
            if key in self.keys or key in ("status", "detail", "target")
        }

    def dumps(self) -> str:
        "`to_dict`で得たものを`ujson.dumps`で文字列にします。"
        return dumps(self.to_dict())

    @classmethod
    def loads(cls, data: str) -> EventContext:
        "JSONからインスタンスを作ります。"
        return cls(**loads(data))
Cog.EventContext = EventContext


class OnErrorContext(EventContext):
    "エラー時のイベントコンテキスト"
    error: Exception

    def make_full_traceback(self) -> str:
        "完全なトレースバックを作成します。"
        return make_error_message(self.error)


EventFunction: TypeAlias = Callable[..., Any | Coroutine]
class RTEvent(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.listeners: defaultdict[str, list[EventFunction]] = \
            defaultdict(list)
        self.set(self.on_error)

    async def on_error(self, ctx: OnErrorContext) -> None:
        self.bot.print("Ignoring error when run event:\n", ctx.make_full_traceback())

    def set(self, function: EventFunction, event_name: Optional[str] = None) -> None:
        "イベントを設定します。"
        event_name = cast(str, event_name or getattr(function, "__name__"))
        is_coro = False
        if iscoroutinefunction(function):
            is_coro = True
            original = function
            @wraps(original)
            async def new_(*args, **kwargs):
                try: return await original(*args, **kwargs)
                except Exception as e:
                    self.dispatch("on_error", OnErrorContext(error=e, function=original))
            function = new_
        else:
            original = function
            @wraps(original)
            def new(*args, **kwargs):
                try: return original(*args, **kwargs)
                except Exception as e:
                    self.dispatch("on_error", OnErrorContext(error=e, function=original))
            function = new
        setattr(function, "__is_coroutine__", is_coro)
        setattr(function, "__event_name__", event_name)
        self.listeners[event_name].append(function)

    def delete(self, target: EventFunction | str) -> None:
        "イベントを削除します。"
        if isinstance(target, str):
            del self.listeners[target]
        else:
            for key in list(self.listeners.keys()):
                if target in self.listeners[key]:
                    self.listeners[key].remove(target)
                    break
            else: raise KeyError("イベントが見つかりませんでした。: %s" % target)

    def dispatch(self, event: str, *args, **kwargs) -> None:
        "イベントを実行します。"
        if event != "on_dispatch":
            self.dispatch("on_dispatch", event, args, kwargs)
        for function in self.listeners[event]:
            coro = function(*args, **kwargs)
            if getattr(function, "__is_coroutine__"):
                create_task(coro, name=f"Run RTEvent: {event}")

    def get_context(self, args: Sequence[EventContext | Any]) -> Optional[EventContext]:
        "引数のシーケンスからEventContextを探します。"
        for arg in args:
            if isinstance(arg, EventContext):
                return arg


async def setup(bot):
    await bot.add_cog(cog := RTEvent(bot))
    bot.rtevent = cog