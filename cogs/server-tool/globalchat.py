# RT - server-tool global
from typing import AsyncIterator, Optional

import discord
from discord.ext import commands

from core import (
    Cog,
    RT,
    t,
    DatabaseManager,
    cursor
)


class DataManager(DatabaseManager):
    def __init__(self, bot: RT):
        self.pool = bot.pool
        self.bot = bot

    async def create_chat(self, name: str, channel: discord.TextChannel) -> bool:
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE name=%s",
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
        await cursor.execute(
            "INSERT INTO GlobalChat VALUES (%s, %s)",
            (name, channel.id)
        )

    async def prepare_table(self) -> None:
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalChat(
                name TEXT, channelid BIGINT);"""
        )

    async def check_exist(self, channel: discord.TextChannel) -> bool:
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE channelid=%s",
            (channel.id,)
        )
        return (await cursor.fetchone()) is not None

    async def check_exist_gc(self, name: str) -> None:
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE name=%s",
            (name,)
        )
        return (await cursor.fetchone()) is not None

    async def get_all_channel(self, name: str) -> AsyncIterator[discord.TextChannel]:
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE name=%s",
            (name,)
        )
        for row in (await cursor.fetchall()):
            yield await self.bot.search_channel(row[1])

    async def get_name(self, channel: discord.TextChannel) -> Optional[str]:
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE channelid=%s",
            (channel.id,)
        )
        data = await cursor.fetchone()
        return data[0] if data is not None else None


class GlobalChat(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(bot)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.group(
        description="Setup global chat",
        aliases=("gc", "gchat")
    )
    async def globalchat(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.reply(t(
                dict(en="Invaild command", ja="使い方が間違っているゾ"),
                ctx
            ))

    @globalchat.command(
        description="Create globalchat",
        aliases=("make", "add")
    )
    async def create(self, ctx, name: str = None):
        if (await self.data.check_exist(ctx.channel)):
            return await ctx.reply(t(
                dict(
                    en="You connected another one.",
                    ja="もうすでにあなたは接続をしています。"
                )
                ,ctx
            ))
        name = "default" if name is None else name
        result = await self.data.create_chat(name, ctx.channel)
        if result:
            await ctx.reply(t(
                dict(
                    en="Created",
                    ja="作成しました。"
                )
                ,ctx))
        else:
            await ctx.reply(t(
                dict(
                    en="Allready created",
                    ja="すでに作成しているゾ"
                ),
                ctx
            ))

    @globalchat.command(
        description="Connect to global chat",
        aliases=("join",)
    )
    async def connect(self, ctx, name: str = None):
        if (await self.data.check_exist(ctx.channel)):
            return await ctx.reply(t(
                dict(
                    en="You connected another one.",
                    ja="もうすでにあなたは接続をしています。"
                )
                ,ctx
            ))
        name = "default" if name is None else name
        if not (await self.data.check_exist_gc(name)):
            return await ctx.reply(t(
                dict(
                    en="Not found",
                    ja="見つかりませんでした。"
                ),
                ctx
            ))
        await self.data.connect(name, ctx.channel)
        await ctx.reply(t(
            dict(
                en="Connected",
                ja="接続しました。"
            ),
            ctx
        ))

    @Cog.listener("on_message")
    async def on_message(self, message):
        if message.author.bot:
            return
        if not (await self.data.check_exist(message.channel)):
            return
        name = await self.data.get_name(message.channel)
        async for channel in self.data.get_all_channel(name):
            print(channel.name)


async def setup(bot: RT):
    await bot.add_cog(GlobalChat(bot))
