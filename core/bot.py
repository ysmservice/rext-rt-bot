# RT - Bot

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, Literal, TypedDict, Any

from functools import wraps
from dataclasses import dataclass

from logging import getLogger
from warnings import warn

from os.path import isdir
from os import listdir
from time import time

from discord.ext import commands
import discord

from discord.ext.fslash import extend_force_slash
from discord.ext.fslash.types_ import InteractionResponseMode

from jishaku.features.baseclass import Feature

from ipcs.client import logger
from ipcs import IpcsClient

from aiomysql import create_pool
from aiohttp import ClientSession
from orjson import dumps

from rtutil.utils import make_random_string

from rtlib.common import set_handler
from rtlib.common.cacher import CacherPool, Cacher
from rtlib.common.chiper import ChiperManager
from rtlib.common.utils import make_simple_error_text

from data import DATA, CATEGORIES, PREFIXES, SECRET, TEST, SHARD, ADMINS, URL, API_URL, Colors

from .rtws import setup
from . import tdpocket

if TYPE_CHECKING:
    from .log import LogCore
    from .rtevent import RTEvent
    from .help import HelpCore
    from .general import Cog, t


__all__ = ("RT",)
set_handler(logger)


class Prefixes(TypedDict):
    Guild: dict[int, str]
    User: dict[int, str]

@dataclass
class Caches:
    guild: dict[int, str]
    user: dict[int, str]


GetT = TypeVar("GetT", bound=discord.abc.Snowflake)
SearchT = TypeVar("SearchT", bound=discord.abc.Snowflake)
class RT(commands.Bot):

    Colors = Colors
    log: LogCore
    rtevent: RTEvent
    exists_caches: Cacher[int, bool]
    help_: HelpCore
    URL = URL
    API_URL = API_URL

    def __init__(self, *args, **kwargs):
        kwargs["command_prefix"] = self._get_command_prefix
        kwargs["help_command"] = None
        if SHARD:
            if DATA["shard_ids"] != "auto":
                kwargs["shard_ids"] = DATA["shard_ids"]
                kwargs["shard_count"] = DATA["shard_count"]
        super().__init__(*args, **kwargs)

        self.prefixes: Prefixes = {"User": {}, "Guild": {}}
        self.language = Caches({}, {})
        self.ipcs = IpcsClient(str(self.shard_id))
        self.ipcs.set_route(self.exists_object, "exists")
        self.chiper = ChiperManager.from_key_file("secret.key")

        extend_force_slash(self, replace_invalid_annotation_to_str=True,
        first_groups=[discord.app_commands.Group(
            name=key, description=CATEGORIES[key]["en"]
        ) for key in CATEGORIES.keys()], context_kwargs={
            "interaction_response_mode": InteractionResponseMode.SEND_AND_REPLY
        })

        self.check(self._guild_check)

    @property
    def signature(self) -> str:
        return self.chiper.encrypt(f"RT.Discord.Bot_{make_random_string(10)}_{time()}")

    def _guild_check(self, ctx: commands.Context) -> bool:
        return ctx.guild is not None

    def _get_command_prefix(self, _, message: discord.Message):
        pr = list(PREFIXES)
        if message.guild is not None and (p := self.prefixes["Guild"].get(message.guild.id, "")):
            pr.append(p)
        if p := self.prefixes["User"].get(message.author.id, ""):
            pr.append(p)
        return pr

    def print(self, *args, **kwargs) -> None:
        "ログ出力をします。"
        print("[RT.Bot]", *args, **kwargs)

    def ignore(self, cog: Cog, error: Any, *args, subject: str = "error:", **kwargs) -> None:
        "出来事が無視されたという旨のログ出力をします。"
        if isinstance(error, Exception):
            error = make_simple_error_text(error)
        self.print(
            "%s [warning] Ignored %s" % (f"[{cog.__cog_name__}]", subject),
            error, *args, **kwargs
        )

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
        self.cachers.start()
        self.exists_caches = self.cachers.acquire(60.0)
        self.print("Prepared cachers")
        self.pool = await create_pool(**SECRET["mysql"])
        self.print("Prepared mysql pool")

        self.session = ClientSession(json_serialize=dumps) # type: ignore

        await self.load_extension("core.rtevent")
        await self.load_extension("core.log")
        await self.load_extension("core.help")
        await self.load_extension("jishaku")
        tdpocket.bot = self
        for path in listdir("cogs"):
            path = f"cogs/{path}"
            if isdir(path):
                for deep in listdir(path):
                    await self._load(f"{path}/{deep}")
            else:
                await self._load(path)
        self.print("Prepared extensions")
        self.dispatch("load")
        self.dispatch("setup")

    async def connect(self, reconnect: bool = True) -> None:
        self.print("Connecting...")
        await super().connect(reconnect=reconnect)

    async def on_connect(self):
        self.print("Connected")
        await self.tree.sync()
        self.print("Command tree was synced")
        self.print("Starting ipcs client...")
        self.ipcs_task = self.loop.create_task(self.ipcs.start(
            uri="{}/rtws?signature={}".format(
                API_URL.replace('http', 'ws'), self.signature
            ),
            port=DATA["backend"]["port"]
        ), name="rt.ipcs")
        self.print("Connected to backend")
        setup(self)
        set_handler(getLogger("discord"))
        self.print("Started")

    async def is_owner(self, user: discord.User) -> bool:
        "オーナーかチェックします。"
        return user.id in ADMINS or await super().is_owner(user)

    def get_language(self, mode: Literal["guild", "user"], id_: int) -> str:
        "指定されたユーザーまたはサーバーの言語設定を取得します。"
        return getattr(self.language, mode).get(id_, "en")

    def search_language(self, guild_id: int | None, user_id: int | None) -> str:
        "ユーザーの言語設定を探して見つからない場合はサーバーの言語設定を`.get_language`で探します。"
        if guild_id is not None and user_id is not None:
            language = self.language.user.get(user_id)
            if language is None:
                language = self.get_language("guild", guild_id)
            return language
        if guild_id is None and user_id is not None:
            return self.get_language("user", user_id)
        elif guild_id is not None and user_id is None:
            return self.get_language("guild", guild_id)
        else:
            return "en"

    async def request(self, route: str, *args, **kwargs) -> Any:
        "バックエンドにリクエストをします。"
        return await self.ipcs.request("__IPCS_SERVER__", route, *args, **kwargs)

    async def exists(self, mode: str, id_: int) -> bool:
        "指定されたオブジェクトがRTが見える範囲に存在しているかを確認します。"
        value = self.exists_caches.get(id_, False)
        if value is None:
            self.exists_caches[id_] = value = await self.ipcs.request(
                "__IPCS_SERVER__", "exists", mode, id_
            )
        return value

    def get_obj(self, attribute: str, id_: int, _: type[GetT]) -> GetT | None:
        """何かを`.get_...`を使用して取得します。
        `.get_...`はBotのシャードが見ている範囲でしか取得することができません。
        そのため、間違えてそれを使用しないように非推奨となっています。
        その非推奨を回避するためのものがこれです。
        詳細は以下をご覧ください。
        (TODO: ここに詳細を書いたウェブページのURLを入れる。)"""
        return getattr(self, f"get_{attribute}")(id_, force=True)

    def get_obj_from_guild(
        self, guild: discord.Guild, attribute: str,
        id_: int, _: type[GetT]
    ) -> GetT | None:
        "`.get_obj`の`discord.Guild`版です。詳細は`.get_obj`のドキュメントをご覧ください。"
        return getattr(guild, attribute)(id_, force=True)

    async def search_user(self, user_id: int) -> discord.User | None:
        "`get_user`または`fetch_user`のどちらかを使用してユーザーデータの取得を試みます。"
        user = self.get_user(user_id)
        if user is None:
            user = await self.fetch_user(user_id)
        return user

    def is_sharded(self) -> bool:
        "シャードが使われているBotかどうかを返します。"
        return hasattr(self, "shard_ids")

    async def search_guild(self, guild_id: int, consider_shard: bool = True) -> discord.Guild | None:
        """`get_guild`または`fetch_guild`のどちらかを使用してギルドデータの取得を試みます。
        これで返されるギルドの`get_member`や`members`そして`channels`などの属性は使えないことがあります。"""
        guild = self.get_guild(guild_id)
        if consider_shard and self.is_sharded() \
                and (guild_id >> 22) % len(getattr(self, "shard_ids")) \
                    in getattr(self, "shard_ids") \
                and guild is None:
            # もし`get_guild`で取得できなかったかつ、ギルドIDから算出したシャードが自分が監視するシャードなら、`fetch_guild`で取得を試みる。
            guild = await self.fetch_guild(guild_id)
        return guild

    async def _search_obj_from_guild(
        self, guild: discord.Guild, id_: int, type_: str,
        type_for_fetch: str | None = None
    ) -> discord.Object | None:
        obj = getattr(guild, f"get_{type_}")(id_)
        if obj is None:
            type_for_fetch = type_for_fetch or type_
            try:
                obj = await getattr(guild, f"fetch_{type_}")(id_)
            except discord.NotFound:
                obj = None
        return obj

    async def search_member(self, guild: discord.Guild, member_id: int) -> discord.Member | None:
        "Guildの`get_member`または`fetch_member`でメンバーオブジェクトの取得を試みます。"
        return await self._search_obj_from_guild(guild, member_id, "member") # type: ignore

    async def search_channel_from_guild(
        self, guild: discord.Guild, channel_id: int
    ) -> discord.abc.GuildChannel | discord.Thread | None:
        "Guildの`get_channel`または`fetch_channel`でチャンネルオブジェクトの取得を試みます。"
        return await self._search_obj_from_guild(
            guild, channel_id, "channel_or_thread", "channel"
        ) # type: ignore

    async def search_channel(self, channel_id: int) \
            -> discord.abc.GuildChannel | discord.Thread | discord.abc.PrivateChannel | None:
        if (channel := self.get_channel(channel_id)) is None:
            channel = await self.fetch_channel(channel_id)
        return channel

    async def close(self):
        self.print("Closing...")
        self.dispatch("close")
        # お片付けをする。
        self.cachers.close()
        self.print("Closed cacher")
        self.pool.close()
        self.print("Closed pool")
        await self.ipcs.close(reason="Closing bot")
        self.print("Closed ipcs")
        return await super().close()

    def exists_object(self, mode: str, id_: int) -> bool:
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


# `get_...`を非推奨とする。
def _mark_get_as_deprecated(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not kwargs.pop("force", False):
            warn("This function is deprecated. Use a function that starts with search_... instead.")
        return func(*args, **kwargs)
    return wrapper
for name in dir(RT):
    if name.startswith("get"):
        setattr(RT, name, _mark_get_as_deprecated(getattr(RT, name)))


# もし本番用での実行またはシャードモードの場合はシャードBotに交換する。
if not TEST or SHARD:
    RT.__bases__ = (commands.AutoShardedBot,)


# Jishakuのコマンドの説明にドキュメンテーションにあるものを入れるようにする。
_original_fc_convert = Feature.Command.convert
@wraps(_original_fc_convert)
def _new_fc_convert(*args, **kwargs):
    command = _original_fc_convert(*args, **kwargs)
    command.description = command.short_doc
    return command
Feature.Command.convert = _new_fc_convert
