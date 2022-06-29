# RT - GlobalChat

from typing import TypedDict, NamedTuple
from collections.abc import AsyncIterator

import discord
from discord.ext import commands

from core import Cog, RT, t, DatabaseManager, cursor

from rtutil.utils import webhook_send
from rtlib.common.json import dumps, loads

from .__init__ import FSPARENT


class Setting(TypedDict, total=False):
    "グローバルチャットの設定"
    password: str | None

class Data(NamedTuple):
    name: str
    author_id: int
    setting: Setting


class DataManager(DatabaseManager):
    "セーブデータを管理します"

    def __init__(self, bot: RT):
        self.pool = bot.pool
        self.bot = bot

    async def prepare_table(self) -> None:
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalChat(
                Name TEXT, AuthorId BIGINT, Setting JSON
            );"""
        )
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalChatMessage(
                Source BIGINT, ChannelId BIGINT PRIMARY KEY NOT NULL,
                MessageId BIGINT
            );"""
        )
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalChatChannel(
                Name TEXT, ChannelId BIGINT
            );"""
        )

    async def connect(self, name: str, channel_id: int) -> None:
        "グローバルチャットに接続します。"
        if await self.is_connected(channel_id, cursor=cursor):
            raise Cog.BadRequest({
                "en": "You are already connected to this globalchat.",
                "ja": "既にこのグローバルチャットに接続しています。"
            })
        await cursor.execute(
            "INSERT INTO GlobalChatChannel VALUES (%s, %s);",
            (name, channel_id)
        )

    async def create(
        self, name: str, author_id: int, channel_id: int, setting: Setting
    ) -> None:
        "主にグローバルチャットを作るために使います。"
        if await self.is_connected(channel_id, cursor=cursor):
            raise Cog.BadRequest({
                "en": "You are already connected to globalchat.",
                "ja": "既にグローバルチャットに接続しています。"
            })
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE Name = %s;",
            (name,)
        )
        if await cursor.fetchone() is not None:
            raise Cog.BadRequest({
                "en": "This globalchat already exists.",
                "ja": "このグローバルチャットは既に存在しています。"
            })
        await cursor.execute(
            "INSERT INTO GlobalChat VALUES (%s, %s, %s);",
            (name, author_id, dumps(setting))
        )
        await cursor.execute(
            "INSERT INTO GlobalChatChannel VALUES (%s, %s);",
            (name, channel_id)
        )

    async def is_connected(self, channel_id: int, **_) -> bool:
        "これはすでに接続されているか確認するものです。"
        await cursor.execute(
            "SELECT * FROM GlobalChatChannel WHERE ChannelId = %s LIMIT 1;",
            (channel_id,)
        )
        return bool(await cursor.fetchone())

    async def is_existed(self, name: str) -> bool:
        "すでにグローバルチャットが存在するか確認します。"
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE Name = %s LIMIT 1;",
            (name,)
        )
        return bool(await cursor.fetchone())

    async def check_password(self, name: str, password: str | None) -> bool | None:
        "パスワードを確認します。"
        await cursor.execute(
            "SELECT Setting FROM GlobalChat WHERE Name = %s LIMIT 1;",
            (name,)
        )
        if row := await cursor.fetchone():
            return loads(row[0])["password"] == password

    async def get_channels(self, name: str, **_) -> AsyncIterator[discord.TextChannel]:
        "グローバルチャットに接続しているチャンネルを名前使って全部取得します。"
        async for (channel_id,) in self.fetchstep(
            cursor, "SELECT ChannelId FROM GlobalChatChannel WHERE Name = %s;", (name,)
        ):
            channel = self.bot.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                yield channel
            else:
                await self.disconnect(channel_id, cursor=cursor)
                self.bot.print(f"[GlobalChat] Delete: {channel_id}")

    async def get_name(self, channel_id: int, **_) -> str | None:
        "チャンネルから接続しているグローバルチャット名を取得します。"
        await cursor.execute(
            "SELECT Name FROM GlobalChatChannel WHERE ChannelId = %s LIMIT 1;",
            (channel_id,)
        )
        if row := await cursor.fetchone():
            return row[0]

    async def disconnect(self, channel_id: int, **_) -> None:
        "グローバルチャットから接続をやめます"
        await cursor.execute(
            "DELETE FROM GlobalChatChannel WHERE ChannelId = %s;",
            (channel_id,)
        )

    async def insert_message(
        self, source: int, channel_id: int, message_id: int
    ) -> None:
        "メッセージを保存します。"
        await cursor.execute(
            "INSERT INTO GlobalChatMessage VALUES (%s, %s, %s);",
            (source, channel_id, message_id)
        )

    async def fetch_global_chat(self, name: str) -> Data:
        "グローバルチャットを取得します。"
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE Name = %s LIMIT 1;",
            (name,)
        )
        if row := await cursor.fetchone():
            return Data(*row)
        else:
            raise Cog.BadRequest({
                "en": "That globalchat does not exist.",
                "ja": "そのグローバルチャットは存在しません。"
            })


class GlobalChat(Cog):
    "グローバルチャットのコグです。"

    WEBHOOK_NAME = "rt-globalchat-webhook"

    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(bot)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.group(
        description="The command of globalchat.",
        aliases=("gc", "gchat"), fsparent=FSPARENT
    )
    async def globalchat(self, ctx):
        await self.group_index(ctx)

    @globalchat.command(description="Create globalchat.", aliases=("make", "add", "作成")
    )
    @discord.app_commands.describe(name="Global chat name", password="Password")
    async def create(self, ctx, name: str, *, password: str | None = None):
        await self.data.create(
            name, ctx.author.id, ctx.channel.id, {
                "password": password
            }
        )
        await ctx.reply(t(dict(
            en="Created", ja="作成しました。"
        ), ctx))

    @globalchat.command(
        description="Connect to global chat.",
        aliases=("join", "参加", "c", "さか")
    )
    @discord.app_commands.describe(name="Global chat name", password="Password")
    async def connect(self, ctx, name: str, *, password: str | None = None):
        if not await self.data.is_existed(name):
            return await ctx.reply(t(dict(
                en="Not found", ja="見つかりませんでした。"
            ), ctx))
        if not await self.data.check_password(name, password):
            return await ctx.reply(t(dict(
                en="Wrong password", ja="パスワードが間違っています。"
            ), ctx))
        await self.data.connect(name, ctx.channel.id)
        await ctx.reply(t(dict(
            en="Connected", ja="接続しました。"
        ), ctx))

    @globalchat.command(
        description="Disconnect from globalchat.",
        aliases=("remove", "rm", "退出", "leave")
    )
    async def disconnect(self, ctx):
        await self.data.disconnect(ctx.channel.id)
        await ctx.reply(t(dict(
            ja="グローバルチャットから退出しました", en="Leave from globalchat"
        ), ctx))

    _help = Cog.HelpCommand(globalchat).merge_description("headline", ja="グローバルチャット関連です。")
    _help.add_sub(Cog.HelpCommand(create)
                  .merge_description("headline", ja="グローバルチャットを作成します。")
                  .add_arg("name", "str", "Optional",
                           ja="グローバルチャット名", en="Globalchat name")
                  .add_arg("password", "str", "Optional",
                           ja="パスワード", en="Password"))
    _help.add_sub(Cog.HelpCommand(connect)
                  .merge_description("headline", ja="グローバルチャットに接続します。")
                  .add_arg("name", "str", "Optional",
                           ja="グローバルチャット名", en="GlobalChat name")
                  .add_arg("password", "str", "Optional",
                           ja="パスワード", en="Password"))
    _help.add_sub(Cog.HelpCommand(disconnect).merge_description(
        "headline", ja="グローバルチャットから退出します。"))
    del _help

    @Cog.listener("on_message")
    async def on_message(self, message: discord.Message):
        if message.author.bot or isinstance(message.author, discord.User):
            return

        async with self.bot.pool.acquire() as connection:
            async with connection.cursor() as cursor:
                if not await self.data.is_connected(message.channel.id, cursor=cursor) or \
                     await self.data.get_name(message.channel.id, cursor=cursor) is None:
                    return
                async for channel in self.data.get_channels(
                    await self.data.get_name(message.channel.id, cursor=cursor), cursor=cursor
                ):
                    if message.channel.id != channel.id:
                        await webhook_send(
                            channel, message.author,
                            message.clean_content,
                            files=[await attachment.to_file() for attachment in message.attachments]
                        )


async def setup(bot: RT) -> None:
    await bot.add_cog(GlobalChat(bot))
