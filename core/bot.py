# RT - Bot

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Optional, Any

from dataclasses import dataclass
from os.path import isdir
from os import listdir

from discord.ext import commands
import discord

from discord.ext.fslash import extend_force_slash, InteractionResponseMode

from ipcs.client import logger
from ipcs import IpcsClient

from aiomysql import create_pool
from aiohttp import ClientSession

from orjson import dumps

from rtlib.common import set_handler

from data import DATA, CATEGORIES, PREFIXES, SECRET, TEST, SHARD, ADMINS, URL, API_URL, Colors

from .cacher import CacherPool, Cacher
from .rtws import setup

if TYPE_CHECKING:
    from .log import LogCore
    from .rtevent import RTEvent


__all__ = ("RT",)
set_handler(logger)


@dataclass
class Caches:
    guild: dict[int, str]
    user: dict[int, str]


class RT(commands.Bot):

    Colors = Colors
    log: LogCore
    rtevent: RTEvent
    exists_caches: Cacher[int, bool]
    URL = URL
    API_URL = API_URL

    def __init__(self, *args, **kwargs):
        kwargs["command_prefix"] = self._get_command_prefix
        kwargs["help_command"] = None
        super().__init__(*args, **kwargs)

        self.prefixes = {}
        self.language = Caches({}, {})
        self.ipcs = IpcsClient(str(self.shard_id))

        extend_force_slash(self, replace_invalid_annotation_to_str=True,
        first_groups=[discord.app_commands.Group(
            name=key, description=CATEGORIES[key]["en"]
        ) for key in CATEGORIES.keys()], context_kwargs={
            "interaction_response_mode": InteractionResponseMode.SEND_AND_REPLY
        })

    def _get_command_prefix(self, _, message: discord.Message):
        return PREFIXES if message.guild is None or message.guild.id not in self.prefixes \
            else PREFIXES + (self.prefixes[message.guild.id],)

    def print(self, *args, **kwargs):
        "ログ出力をします。"
        print("[RT.Bot]", *args, **kwargs)

    async def _load(self, path: str):
        if path.endswith(".py") or isdir(path):
            try:
                await self.load_extension(path.replace("/", ".").replace(".py", ""))
            except commands.NoEntryPointError as e:
                if "'setup'" not in str(e): raise
            else:
                self.print("Load extension:", path)

    async def setup_hook(self):
        self.cachers = CacherPool()
        self.exists_caches = self.cachers.acquire(60.0)
        self.print("Prepared cachers")
        self.pool = await create_pool(**SECRET["mysql"])
        self.print("Prepared mysql pool")

        self.session = ClientSession(json_serialize=dumps) # type: ignore

        await self.load_extension("core.rtevent")
        await self.load_extension("core.log")
        self.log = self.cogs["LogCore"] # type: ignore
        await self.load_extension("jishaku")
        for path in listdir("cogs"):
            path = f"cogs/{path}"
            if isdir(path):
                for deep in listdir(path):
                    await self._load(f"{path}/{deep}")
            else:
                await self._load(path)
        self.print("Prepared extensions")
        self.dispatch("load")

    async def connect(self, reconnect: bool = True) -> None:
        self.print("Connecting...")
        await super().connect(reconnect=reconnect)

    async def on_connect(self):
        self.print("Connected")
        await self.tree.sync()
        self.print("Command tree was synced")
        self.print("Starting ipcs client...")
        self.loop.create_task(self.ipcs.start(
            uri=f"{API_URL.replace('http', 'ws')}/rtws",
            port=DATA["backend"]["port"]
        ), name="rt.ipcs")
        self.print("Connected to backend")
        setup(self)
        self.print("Started")

    async def is_owner(self, user: discord.User) -> bool:
        "オーナーかチェックします。"
        return user.id in ADMINS

    def get_language(self, mode: Literal["guild", "user"], id_: int) -> str:
        "指定されたユーザーまたはサーバーの言語設定を取得します。"
        return getattr(self.language, mode).get(id_, "en")

    async def request(self, route: str, *args, **kwargs) -> Any:
        "バックエンドにリクエストをします。"
        return await self.ipcs.request("__IPCS_SERVER__", route, *args, **kwargs)

    async def exists_all(self, mode: str, id_: int) -> bool:
        "指定されたオブジェクトがRTが見える範囲に存在しているかを確認します。"
        value = self.exists_caches.get(id_, False)
        if value is None:
            self.exists_caches[id_] = value = await self.ipcs.request(
                "__IPCS_SERVER__", "exists", mode, id_
            )
        return value

    async def search_user(self, user_id: int) -> Optional[discord.User]:
        "`get_user`または`fetch_user`のどちらかを使用してユーザーデータの取得を試みます。"
        user = super().get_user(user_id)
        if user is None:
            user = await self.fetch_user(user_id)
        return user

    async def get_member(self, guild: discord.Guild, member_id: int) -> Optional[discord.Member]:
        "Guildの`get_member`または`fetch_member`でメンバーオブジェクトの取得を試みます。"
        member = guild.get_member(member_id)
        if member is None:
            member = await guild.fetch_member(member_id)
        return member

    async def close(self):
        self.print("Closing...")
        self.dispatch("close")
        # お片付けをする。
        self.pool.close()
        self.print("Closed pool")
        await self.ipcs.close(reason="Closing bot")
        self.print("Closed ipcs")
        return await super().close()

    def exists(self, mode: str, id_: int) -> bool:
        "指定されたIDの存在確認をします。"
        return getattr(self, f"get_{mode}")(id_) is not None

    @property
    def round_latency(self) -> str:
        "綺麗にしたレイテンシの文字列を取得します。"
        return "%.1f" % round(self.latency * 1000, 1)

    @property
    def parsed_latency(self) -> str:
        "`round_latency`で取得した文字列の後ろに`ms`を最後に付けた文字列を取得します。"
        return f"{self.round_latency}ms"


# もし本番用での実行またはシャードモードの場合はシャードBotに交換する。
if not TEST or SHARD:
    RT.__bases__ = (commands.AutoShardedBot,)