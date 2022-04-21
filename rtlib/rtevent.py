# RT - RT Event

from __future__ import annotations

from typing import Any

from ujson import loads, dumps

from .general import Cog, RT


__all__ = ("EventContext",)


class EventContext:
    "イベントデータを格納する`Context`のベースです。"

    def __init__(self, **kwargs):
        self.keys = []
        for key, value in kwargs.items():
            setattr(self, key, value)
            self.keys.append(key)

    def to_dict(self) -> dict[str, Any]:
        "格納されているデータを辞書にします。"
        return {
            key: value for key, value in self.__dict__.items()
            if key in self.keys
        }

    def dumps(self) -> str:
        "`to_dict`で得たものを`ujson.dumps`で文字列にします。"
        return dumps(self.to_dict())

    @classmethod
    def loads(cls, data: str) -> EventContext:
        "JSONからインスタンスを作ります。"
        return cls(**loads(data))
Cog.EventContext = EventContext


class RTEvent(Cog):
    def __init__(self, bot: RT):
        self.bot = bot


def setup(bot):
    bot.add_cog(RTEvent(bot))