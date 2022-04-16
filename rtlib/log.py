# RT - Log Data Class

from __future__ import annotations

from typing import TypeAlias, Optional

from dataclasses import dataclass
from enum import Enum
from time import time

from discord.ext.commands import Context
import discord

from aiomysql import Pool

from .types_ import CmdGrp, UserMember
from .database import DatabaseManager, cursor
from .utils import get_inner_text
from .help import Help
from .general import RT, Cog

from data import EMOJIS, TEST


__all__ = ("IdType", "ProcessType", "LogData", "detect_type", "DataManager")


class IdType(Enum):
    "IDの種類です。"

    guild = 1
    user = 2


class ProcessType(Enum):
    "処理内容の種類です。"

    command = 1
    "コマンド実行"
    working = 2
    "機能実行"


class ResultType(Enum):
    "処理結果の種類です。"

    success = 1
    warning = 2
    error = 3
    unknown = 4


RESULT_TEXT = {
    "warning": {"ja": "警告", "en": "Warning"},
    "error": {"ja": "エラー", "en": "Error"},
    "unknown": {"ja": "不明", "en": "Unknown"},
    "success": {"ja": "成功", "en": "Success"}
}


Target: TypeAlias = discord.Guild | UserMember
@dataclass
class LogData:
    "RTの処理ログのデータクラスです。"

    target: Target
    process_type: ProcessType
    result_type: ResultType
    time_: int
    feature_name: str
    feature_category: str
    detail: str
    ctx: Optional[Context] = None

    @classmethod
    def quick_make(
        cls, feature: CmdGrp | tuple[str, str],
        result_type: ResultType, target: Target,
        detail: str, time_: Optional[float] = None,
        process_type: ProcessType = ProcessType.working,
        **kwargs
    ) -> LogData:
        "楽にLogDataオブジェクトを作るための関数です。"
        if isinstance(feature, tuple):
            category, name = feature
        else:
            help_: Optional[Help] = getattr(feature.callback, "__help__", None)
            name = feature.name
            category = help_.category if help_ else "Other"
        return cls(
            target, process_type, result_type, int(time_ or time()),
            name, category, detail, **kwargs
        )

    def to_str(self, language: str) -> str:
        "データ内容を文字列に変換します。"
        return "**{}@{}**\n<t:{}> {}{}\n{}".format(
            self.feature_name, self.feature_category, self.time_, "{}{}".format(
                EMOJIS.get(self.result_type.name), get_inner_text(
                    RESULT_TEXT, self.result_type.name, language
                )
            ), self.detail
        )


def detect_type(data: LogData) -> IdType:
    "IDの種類を割り出します。"
    return IdType.guild if isinstance(data.target, discord.Guild) else IdType.user


class DataManager(DatabaseManager):
    "RTの処理ログのデータを管理するためのクラスです。"

    TIMEOUT = 3600 if TEST else 259200
    "何秒までログデータを保持するかです。"

    def __init__(self, pool: Pool):
        self.pool = pool

    async def prepare_table(self) -> None:
        "テーブルを準備します。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS Log (
                Id BIGINT, IdType TINYINT, ProcessType TINYINT, ResultType TINYINT,
                Time INTEGER, FeatureCategory TEXT, FeatureName TEXT, Detail TEXT
            );"""
        )

    async def add(self, data: LogData) -> None:
        "ログを追加します。"
        await cursor.execute(
            "INSERT INTO Log VALUES (%s, %s, %s, %s, %s, %s, %s, %s);",
            (
                data.target.id, detect_type(data).value, data.process_type.value,
                data.result_type.value, data.time_, data.feature_category,
                data.feature_name, data.detail
            )
        )

    async def clear(self, id_: int) -> None:
        "指定されたIDのログを全て消去します。"
        await cursor.execute("DELETE FROM Log WHERE Id = %s;", (id_,))

    async def clean(self) -> None:
        "古いデータを消します。\n`.TIMEOUT`秒経過したデータが消去対象です。"
        now = time()
        await cursor.execute("SELECT Id, Time FROM Log;")
        for row in await cursor.fetchall():
            if now - row[1] >= self.TIMEOUT:
                await cursor.execute(
                    "DELETE FROM Log WHERE Id = %s AND Time = %s;",
                    row
                )


class LogCore(Cog):
    "RTのログを簡単に追加したりするためのものです。"

    IdType = IdType
    ProcessType = ProcessType
    ResultType = ResultType
    LogData = LogData

    def __init__(self, bot: RT):
        self.bot, self.data = bot, DataManager(bot.pool)

    async def cog_load(self):
        await self.data.prepare_table()

    async def __call__(self, data: LogData):
        self.bot.dispatch("log", data)
        await self.data.add(data)


async def setup(bot):
    await bot.add_cog(LogCore(bot))