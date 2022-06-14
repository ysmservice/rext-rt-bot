# RT - server-tool global

from typing import Optional

from collections.abc import AsyncIterator
from functools import partial

import discord
from discord.ext import commands

from core import Cog, RT, t, DatabaseManager, cursor

from .__init__ import fsparent


class DataManager(DatabaseManager):
    "グローバルチャットのデータベースを管理します。"

    def __init__(self, bot: RT):
        self.pool = bot.pool
        self.bot = bot

    async def create_chat(
        self, name: str, channel: discord.TextChannel
    ) -> bool:
        "主にグローバルチャットを作るために使います。"
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE name = %s",
            (name,)
        )
        if (await cursor.fetchone()) is not None:
            return False
        await cursor.execute(
            "INSERT INTO GlobalChat VALUES (%s, %s)",
            (name, channel.id)
        )
        return True

    async def connect(self, name: str, channel: discord.TextChannel) -> None:
        "グローバルチャットに接続します。"
        await cursor.execute(
            "INSERT INTO GlobalChat VALUES (%s, %s)",
            (name, channel.id)
        )

    async def prepare_table(self) -> None:
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalChat(
                name TEXT, channelid BIGINT
            );"""
        )
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalChatMessage(
                source BIGINT, channelid BIGINT, messageid BIGINT
            );"""
        )

    async def check_exist(self, channel: discord.TextChannel) -> bool:
        "これはすでに接続されているか確認するものです。"
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE channelid = %s",
            (channel.id,)
        )
        return (await cursor.fetchone()) is not None

    async def check_exist_gc(self, name: str) -> bool:
        "すでにグローバルチャットが存在するか確認します。"
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE name = %s",
            (name,)
        )
        return (await cursor.fetchone()) is not None

    async def get_all_channel(
        self, name: str
    ) -> AsyncIterator[discord.TextChannel]:
        "グローバルチャットに接続しているチャンネルを名前使って全部取得します。"
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE name = %s",
            (name,)
        )
        for _, channelid in await cursor.fetchall():
            channel = await self.get_channel(channelid)
            if channel is None:
                await self.disconnect(channel)
            else:
                yield channel

    async def get_channel(
        self, channelid: int
    ) -> Optional[discord.TextChannel]:
        "チャンネルを取得します。"
        channel = await self.bot.loop.run_in_executor(
            None, partial(self.bot.get_channel, channelid)
        )
        if channel is not None:
            return channel
        else:
            try:
                return await self.bot.fetch_channel(channelid)
            except discord.errors.NotFound:
                return None

    async def get_name(self, channel: discord.TextChannel) -> Optional[str]:
        "チャンネルから接続しているグローバルチャット名を取得します。"
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE channelid = %s",
            (channel.id,)
        )
        data = await cursor.fetchone()
        return data[0] if data is not None else None

    async def disconnect(self, channel: discord.TextChannel) -> None:
        "グローバルチャットから接続をやめます"
        await cursor.execute(
            "DELETE FROM GlobalChat WHERE channelid = %s", (channel.id,)
        )

    async def insert_message(
        self, source: int, channelid: int, message: discord.WebhookMessage
    ) -> None:
        await cursor.execute(
            "INSERT INTO GlobalChatMessage VALUES(%s, %s, %s);",
            (source, channelid, message.id)
        )


class GlobalChat(Cog):

    "グローバルチャットのコグです。"

    WEBHOOK_NAME: str = "rt-globalchat-webhook"

    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(bot)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.group(
        description="Setup global chat",
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
    async def create(self, ctx, name: str = None):
        if (await self.data.check_exist(ctx.channel)):
            return await ctx.reply(t(
                dict(en="You connected another one.", ja="もうすでにあなたは接続をしています。"),
                ctx
            ))
        result = await self.data.create_chat(
            "default" if name is None else name, ctx.channel
        )
        if result:
            await ctx.reply(t(
                dict(en="Created", ja="作成しました。"), ctx
            ))
        else:
            await ctx.reply(t(
                dict(
                    en="Allready created",
                    ja="すでに作成しているゾ"
                ), ctx
            ))

    @globalchat.command(
        description="Connect to global chat",
        aliases=("join", "参加")
    )
    @discord.app_commands.describe(name="Global chat name")
    async def connect(self, ctx, name: str = None):
        if (await self.data.check_exist(ctx.channel)):
            return await ctx.reply(t(
                dict(en="You connected another one.", ja="もうすでにあなたは接続をしています。"), ctx
            ))
        name = "default" if name is None else name
        if not (await self.data.check_exist_gc(name)):
            return await ctx.reply(t(
                dict(en="Not found", ja="見つかりませんでした。"), ctx
            ))
        await self.data.connect(name, ctx.channel)
        await ctx.reply(t(
            dict(en="Connected", ja="接続しました。"), ctx
        ))

    @globalchat.command(
        description="Disconnect from globalchat",
        aliases=("remove", "rm", ")
    )
    async def leave(self, ctx):
        await self.data.disconnect(ctx.channel)
        await ctx.reply(t(
            dict(ja="グローバルチャットから退出しました", en="Leave from globalchat"), ctx
        ))

    (Cog.HelpCommand(globalchat)
        .merge_description("headline", ja="グローバルチャット関連です。") \
        .add_sub(Cog.HelpCommand(create)
                     .merge_description("headline", ja="グローバルチャットを作成します。")
                     .add_arg("name", "str", "Optional",
                          ja="グローバルチャット名",
                          en="Globalchat name")
                 ) \
        .add_sub(Cog.HelpCommand(connect)
                     .merge_description("headline", ja="グローバルチャットに接続します。")
                     .add_arg("name", "str", "Optional",
                          ja="グローバルチャット名",
                          en="GlobalChat name")
                 ) \
        .add_sub(Cog.HelpCommand(leave).merge_description("headline", ja="グローバルチャットから退出します。"))
    )

    @Cog.listener("on_message")
    async def on_message(self, message):
        if message.author.bot:
            return
        if not (await self.data.check_exist(message.channel)):
            return
        async for channel in self.data.get_all_channel(
            await self.data.get_name(message.channel)
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
                username=f"{message.author.display_name}({message.author.id}",
                avatar_url=getattr(message.author.avatar, "url", None)
            )


async def setup(bot: RT) -> None:
    await bot.add_cog(GlobalChat(bot))
