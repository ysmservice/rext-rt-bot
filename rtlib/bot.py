# RT - Bot

from typing import Literal, Optional

from dataclasses import dataclass
from os.path import isdir
from os import listdir

from discord.ext import commands
from discord.ext.fslash import extend_force_slash
import discord

from aiomysql import create_pool
from aiohttp import ClientSession
from ujson import dumps

from data.constants import PREFIXES, ADMINS, Colors
from data import SECRET

from .cacher import CacherPool


__all__ = ("RT",)


@dataclass
class Caches:
    guild: dict[int, str]
    user: dict[int, str]


class RT(commands.AutoShardedBot):

    Colors = Colors

    def __init__(self, *args, **kwargs):
        self.session = ClientSession(json_serialize=dumps)

        kwargs["intents"] = discord.Intents.default()
        kwargs["intents"].message_content = True
        kwargs["intents"].members = True
        kwargs["status"] = discord.Status.dnd
        kwargs["activity"] = discord.Game("起動")
        kwargs["command_prefix"] = self._get_command_prefix
        kwargs["help_command"] = None
        super().__init__(*args, **kwargs)

        self.prefixes = {}
        self.language = Caches({}, {})

        extend_force_slash(self, replace_invalid_annotation_to_str=True)

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
        self.print("Prepared cachers")
        self.pool = await create_pool(**SECRET["mysql"])
        self.print("Prepared mysql pool")
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
        self.print("Connected")
        await self.tree.sync()
        self.print("Command tree was synced")
        self.print("Started")

    async def is_owner(self, user: discord.User) -> bool:
        return user.id in ADMINS

    def get_language(self, mode: Literal["guild", "user"], id_: int) -> str:
        "Get language setting from user/guild id."
        return getattr(self.language, mode).get(id_, "en")

    async def get_user(self, user_id: int) -> Optional[discord.User]:
        "get/fetch user"
        user = super().get_user(user_id)
        if user is None:
            user = await self.fetch_user(user_id)
        return user

    async def get_member(self, guild: discord.Guild, member_id: int) -> Optional[discord.Member]:
        "get/fetch member from guild"
        member = guild.get_member(member_id)
        if member is None:
            member = await guild.fetch_member(member_id)
        return member

    async def close(self):
        self.print("Closing...")
        self.dispatch("close")
        # お片付けをする。
        self.pool.close()
        return await super().close()

    @property
    def round_latency(self) -> str:
        "Get round latency"
        return "%.1f" % round(self.latency * 1000, 1)

    @property
    def parsed_latency(self) -> str:
        "Get parsed latency"
        return f"{self.round_latency}ms"