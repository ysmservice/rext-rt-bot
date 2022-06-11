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
from .utils import get_inner_text
from .help import Help
from .general import RT, Cog

from rtlib.common.database import DatabaseManager, cursor

from data import EMOJIS, TEST, CANARY


__all__ = (
    "IdType", "ProcessType", "LogData", "detect_type", "DataManager", "Feature", "Target"
)


class IdType(Enum):
    "IDの種類です。"

    GUILD = 1
    USER = 2


class ProcessType(Enum):
    "処理内容の種類です。"

    COMMAND = 1
    "コマンド実行"
    WORKING = 2
    "機能実行"


class ResultType(Enum):
    "処理結果の種類です。"

    SUCCESS = 1
    WARNING = 2
    ERROR = 3
    UNKNOWN = 4


RESULT_TEXT = {
    "WARNING": {"ja": "警告", "en": "Warning"},
    "ERROR": {"ja": "エラー", "en": "Error"},
    "UNKNOWN": {"ja": "不明", "en": "Unknown"},
    "SUCCESS": {"ja": "成功", "en": "Success"}
}


Target: TypeAlias = discord.Guild | UserMember | int
Feature: TypeAlias = CmdGrp | tuple[str, str]
@dataclass
class LogData:
    "RTの処理ログのデータクラスです。"

    id: int
    id_type: IdType
    process_type: ProcessType
    result_type: ResultType
    time: int
    feature_category: str
    feature_name: str
    detail: str
    ctx: Optional[Context] = None
    target: Optional[Target] = None

    @classmethod
    def quick_make(
        cls, feature: Feature, result_type: ResultType | str,
        target: Target, detail: str, time_: Optional[float] = None,
        process_type: ProcessType | str = ProcessType.WORKING,
        **kwargs
    ) -> LogData:
        "楽にLogDataオブジェクトを作るための関数です。"
        if isinstance(feature, tuple):
            category, name = feature
        else:
            help_: Optional[Help] = getattr(feature.callback, "__help__", None)
            name = feature.name
            category = help_.category if help_ else "Other"
        kwargs["target"] = target
        return cls(
            getattr(target, "id", target), # type: ignore
            IdType.GUILD if isinstance(target, discord.Guild) else IdType.USER,
            getattr(ProcessType, process_type) if isinstance(process_type, str) else process_type,
            getattr(ResultType, result_type) if isinstance(result_type, str) else result_type,
            int(time_ or time()), category, name, detail, **kwargs
        )

    def title(self, language: str) -> str:
        "タイトルを作ります。"
        return "{}/{} <t:{}> {} {}".format(
            self.feature_name, self.feature_category, self.time,
            EMOJIS.get(self.result_type.name.lower()), get_inner_text(
                RESULT_TEXT, self.result_type.name, language
            )
        )

    def to_str(self, language: str, contain_title: bool = True) -> str:
        "データ内容を文字列に変換します。\nタイトルを作らないのなら`language`はなんだって良いです。"
        return "{}{}".format(
            f"{self.title(language)}\n" if contain_title else "", self.detail
        )


def detect_type(data: LogData) -> IdType:
    "IDの種類を割り出します。"
    return IdType.GUILD if isinstance(data.target, discord.Guild) else IdType.USER


class DataManager(DatabaseManager):
    "RTの処理ログのデータを管理するためのクラスです。"

    TIMEOUT = 3600 if TEST else 259200
    "何秒までログデータを保持するかです。"
    MAX_RECORDS = 30 if TEST and not CANARY else 50000
    "何個までログデータを保存するかです。"

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
                data.id, data.id_type.value, data.process_type.value,
                data.result_type.value, data.time, data.feature_category,
                data.feature_name, data.detail
            )
        )
        # もしログデータが大量にある場合は、古いレコードを消して最大レコードの数だけにする。
        await cursor.execute(
            "SELECT Id, Time FROM Log ORDER BY Time DESC LIMIT %s, 1;",
            (self.MAX_RECORDS - 1,)
        )
        if row := await cursor.fetchone():
            await cursor.execute(
                "DELETE FROM Log WHERE Id = %s AND Time < %s;", row
            )

    async def clear(self, id_: int) -> None:
        "指定されたIDのログを全て消去します。"
        await cursor.execute("DELETE FROM Log WHERE Id = %s;", (id_,))

    async def clean(self) -> None:
        "古いデータを消します。\n`.TIMEOUT`秒経過したデータが消去対象です。"
        now = time()
        await cursor.execute("SELECT Id, Time FROM Log;")
        async for row in self.fetchstep(cursor, "SELECT Id, Time FROM Log;"):
            if now - row[1] >= self.TIMEOUT:
                await cursor.execute(
                    "DELETE FROM Log WHERE Id = %s AND Time = %s;",
                    row
                )

    def row_to_data(self, row: tuple) -> LogData:
        "渡されたレコードのデータからLogDataオブジェクトを作ります。"
        return LogData(
            row[0], IdType(row[1]), ProcessType(row[2]), ResultType(row[3]),
            row[4], row[5], row[6], row[7]
        )


class LogCore(Cog):
    "RTのログを簡単に追加したりするためのものです。"

    IdType = IdType
    ProcessType = ProcessType
    ResultType = ResultType
    LogData = LogData

    def __init__(self, bot: RT):
        self.bot, self.data = bot, DataManager(bot.pool)
        self.bot.log = self
        self.bot.rtevent.set(self.on_dispatch)

    async def cog_load(self):
        await self.data.prepare_table()

    async def on_dispatch(self, ctx: Cog.EventContext):
        # RTイベントで`log`が`True`のContextが引数にある場合は、ログに流す。
        assert ctx.target is not None
        await self.__call__(LogData.quick_make(
            ctx.feature, ctx.status, ctx.target, ctx.detail
        ))

    async def __call__(self, data: LogData):
        self.bot.dispatch("log", data)
        await self.data.add(data)


async def setup(bot):
    await bot.add_cog(LogCore(bot))