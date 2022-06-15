# RT - server-tool global

from typing import Dict, Any

from collections.abc import AsyncIterator
from functools import partial

import discord
from discord.ext import commands

from orjson import dumps

from core import Cog, RT, t, DatabaseManager, cursor

from .__init__ import FSPARENT


class DataManager(DatabaseManager):
    "グローバルチャットのデータベースを管理します。"

    def __init__(self, bot: RT):
        self.pool = bot.pool
        self.bot = bot

    async def connect(self, name: str, channelid: int) -> None:
        "グローバルチャットに接続します。"
        await cursor.execute(
            "INSERT INTO GlobalChatChannel VALUES (%s, %s);", (name, channelid)
        )

    async def create_chat(
        self, name: str, author_id: int, channel_id: int, settings: Dict[str, Any]
    ) -> bool:
        "主にグローバルチャットを作るために使います。"
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE name = %s;",
            (name,)
        )
        if (await cursor.fetchone()) is not None:
            return False
        await cursor.execute(
            "INSERT INTO GlobalChat VALUES (%s, %s, %s);",
            (name, author_id, dumps(settings))
        )
        await cursor.execute(
            "INSERT INTO GlobalChatChannel VALUES (%s, %s);",
            (name, channel_id)
        )
        return True

    async def prepare_table(self) -> None:
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalChat(
                Name TEXT, AuthorId BIGINT PRIMARY KEY NOT NULL, Setting JSON
            );"""
        )
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalChatMessage(
                Source BIGINT, ChannelId BIGINT, MessageId BIGINT
            );"""
        )
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalChatChannel(
                Name TEXT, ChannelId BIGINT
            );"""
        )

    async def is_connected(self, channel_id: int) -> bool:
        "これはすでに接続されているか確認するものです。"
        await cursor.execute(
            "SELECT * FROM GlobalChatChannel WHERE ChannelId = %s;",
            (channel_id,)
        )
        return bool(await cursor.fetchone())

    async def check_exists(self, name: str, password: str = None) -> bool:
        "すでにグローバルチャットが存在するか確認します。"
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE Name = %s AND Setting = %s;",
            (name, dumps({"password": password}))
        )
        return bool(await cursor.fetchone())

    async def get_all_channel(
        self, name: str
    ) -> AsyncIterator[discord.TextChannel]:
        "グローバルチャットに接続しているチャンネルを名前使って全部取得します。"
        await cursor.execute(
            "SELECT * FROM GlobalChatChannel WHERE Name = %s;",
            (name,)
        )
        for _, channel_id in await cursor.fetchall():
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                await self.disconnect(channel, cursor=cursor)
            else:
                yield channel

    async def get_name(self, channel_id: int) -> str | None:
        "チャンネルから接続しているグローバルチャット名を取得します。"
        await cursor.execute(
            "SELECT * FROM GlobalChatChannel WHERE ChannelId = %s;",
            (channel_id,)
        )
        if row := await cursor.fetchone():
            return row[0]

    async def disconnect(self, channel_id: int, **kwargs) -> None:    
        "グローバルチャットから接続をやめます"
        await cursor.execute(
            "DELETE FROM GlobalChatChannel WHERE ChannelId = %s;", (channel_id,)
        )

    async def insert_message(
        self, source: int, channel_id: int, message_id: int
    ) -> None:
        "メッセージを保存します。"
        await cursor.execute(
            "INSERT INTO GlobalChatMessage VALUES(%s, %s, %s);",
            (source, channel_id, message_id)
        )


class GlobalChat(Cog):

    "グローバルチャットのコグです。"

    WEBHOOK_NAME = "rt-globalchat-webhook"

    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(bot)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.group(
        description="The command of globalchat.に",
        aliases=("gc", "gchat"),
        fsparent=FSPARENT
    )
    async def globalchat(self, ctx):
        await self.group_index(ctx)

    @globalchat.command(
        description="Create globalchat",
        aliases=("make", "add", "作成")
    )
    @discord.app_commands.describe(name="Global chat name")
    async def create(self, ctx, name: str = None, password: str = None):
        if await self.data.is_connected(ctx.channel.id):
            return await ctx.reply(t(dict(
                en="You connected another one.", ja="もうすでにあなたは接続をしています。"
            ), ctx))
        result = await self.data.create_chat(
            "default" if name is None else name, ctx.author.id, ctx.channel.id, {"password": password}
        )
        if result:
            await ctx.reply(t(dict(
                en="Created", ja="作成しました。"
            ), ctx))
        else:
            await ctx.reply(t(dict(
                en="Allready created", ja="すでに作成しているゾ"
            ), ctx))

    @globalchat.command(
        description="Connect to global chat",
        aliases=("join", "参加")
    )
    @discord.app_commands.describe(name="Global chat name")
    async def connect(self, ctx, name: str = None, password = None):
        if await self.data.is_connected(ctx.channel.id):
            return await ctx.reply(t(dict(
                en="You connected another one.", ja="もうすでにあなたは接続をしています。"
            ), ctx))
        name = "default" if name is None else name
        if not await self.data.check_exists(name, password):
            return await ctx.reply(t(dict(
                en="Not found", ja="見つかりませんでした。"
            ), ctx))
        await self.data.connect(name, ctx.channel.id)
        await ctx.reply(t(dict(
            en="Connected", ja="接続しました。"
        ), ctx))

    @globalchat.command(
        description="Disconnect from globalchat",
        aliases=("remove", "rm", "退出")
    )
    async def leave(self, ctx):
        await self.data.disconnect(ctx.channel.id)
        await ctx.reply(t(dict(
            ja="グローバルチャットから退出しました", en="Leave from globalchat"
        ), ctx))

    (Cog.HelpCommand(globalchat)
        .merge_description("headline", ja="グローバルチャット関連です。")
        .add_sub(Cog.HelpCommand(create)
                 .merge_description("headline", ja="グローバルチャットを作成します。")
                 .add_arg("name", "str", "Optional",
                          ja="グローバルチャット名",
                          en="Globalchat name")
                 )
        .add_sub(Cog.HelpCommand(connect)
                 .merge_description("headline", ja="グローバルチャットに接続します。")
                 .add_arg("name", "str", "Optional",
                          ja="グローバルチャット名",
                          en="GlobalChat name")
                 )
        .add_sub(Cog.HelpCommand(leave).merge_description("headline", ja="グローバルチャットから退出します。"))
     )

    @Cog.listener("on_message")
    async def on_message(self, message):
        if message.author.bot:
            return
        if not await self.data.is_connected(message.channel.id):
            return
        async for channel in self.data.get_all_channel(
            await self.data.get_name(message.channel.id)
        ):
            if message.channel.id == channel.id:
                continue
            webhook = discord.utils.get(
                await channel.webhooks(), name=self.WEBHOOK_NAME
            )
            if webhook is None:
                webhook = await channel.create_webhook(
                    name=self.WEBHOOK_NAME
                )
            await webhook.send(
                message.clean_content,
                username=f"{message.author.display_name}({message.author.id})",
                avatar_url=getattr(message.author.avatar, "url", None)
            )


async def setup(bot: RT) -> None:
    await bot.add_cog(GlobalChat(bot))
