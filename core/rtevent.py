# RT - RT Event

from __future__ import annotations

from typing import TypeAlias, Optional, Any, cast
from collections.abc import Callable, Coroutine, Sequence

from asyncio import create_task
from inspect import iscoroutinefunction
from collections import defaultdict
from functools import wraps

from orjson import loads, dumps

from rtlib.common.utils import make_error_message

from .log import Feature, Target
from .general import Cog, RT, t
from .types_ import Text


__all__ = ("EventContext", "OnErrorContext", "RTEvent")


class EventContext:
    "イベントデータを格納する`Context`のベースです。"

    event: str

    def __init__(
        self, bot: RT, target: Optional[Target | int] = None, status: str = "SUCCESS",
        subject: str | Text = "", detail: str | Text = "",
        feature: Feature = ("Unknown", "..."),
        log: bool = True, **kwargs
    ):
        self.keys = []
        for key, value in kwargs.items():
            setattr(self, key, value)
            self.keys.append(key)
        self.log, self.status, self.target = log, status, target
        # 文字列はもし辞書の場合は`t`を通す。
        if isinstance(subject, dict):
            subject = t(subject, target, client=bot)
        if isinstance(detail, dict):
            detail = t(detail, target, client=bot)
        self.detail = "{}{}".format(
            f"{subject}\n" if subject and detail else "",
            detail
        )
        self.feature = feature

    def to_dict(self) -> dict[str, Any]:
        "格納されているデータを辞書にします。"
        return {
            key: value for key, value in self.__dict__.items()
            if key in self.keys or key in ("event", "status", "detail", "target", "feature")
        }

    def dumps(self) -> str:
        "`to_dict`で得たものを`orjson.dumps`で文字列にします。"
        return dumps(self.to_dict()).decode()

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
                    self.dispatch("on_error", OnErrorContext(self.bot, error=e, function=original))
            function = new_
        else:
            original = function
            @wraps(original)
            def new(*args, **kwargs):
                try: return original(*args, **kwargs)
                except Exception as e:
                    self.dispatch("on_error", OnErrorContext(self.bot, error=e, function=original))
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

    def dispatch(self, event: str, context: EventContext) -> None:
        "イベントを実行します。"
        context.event = event
        if event != "on_dispatch":
            self.dispatch("on_dispatch", context)
        for function in self.listeners[event]:
            coro = function(context)
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