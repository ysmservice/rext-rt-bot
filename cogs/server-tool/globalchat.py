# RT - server-tool global
import discord
from discord.ext import commands

from core import Cog, RT, t, DatabaseManager, cursor


class DataManager(DatabaseManager):
    def __init__(self, bot: RT):
        self.pool = bot.pool

    async def create_chat(self, name: str, channel: discord.TextChannel) -> bool:
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE name=%s",
            (name, channel.id)
        )
        if (await cursor.fetchone()) is None:
            return False
        await cursor.execute(
            "INSERT INTO GlobalChat VALUES(%s, %s);",
            (name, channel.id)
        )
        return True

    async def prepare_table(self) -> None:
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalChat(
                name TEXT, channelid BIGINT
            );"""
        )

    async def check_exist(self, channel: discord.TextChannel) -> None:
        await cursor.execute(
            "SELECT * FROM GlobalChannel WHERE channelid=%s",
            (channel.id,)
        )
        return (await cursor.fetchone()) is not None


class GlobalChat(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(bot)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.group(
        description="Setup global chat"
        aliases=("gc", "gchat")
    )
    async def globalchat(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.reply(t(ctx, dict(en="Invaild command", ja="使い方が間違っているゾ")))

    @globalchat.command(
        description="Create globalchat",
        aliases=("make", "add")
    )
    async def create(self, ctx, name: str = None):
        if (await self.data.check_exist(ctx.channel)):
            return await ctx.reply(t(ctx, dict(en="You connected another one.", ja="もうすでにあなたは接続をしています。")))
        name = "default" if name is None else name
        result = await self.data.create_chat(name, ctx.channel)
        if result:
            await ctx.reply(t(ctx, dict(en="Created", ja="作成しました。")))
        else:
            await ctx.reply(t(ctx, dict(en="Allready created", ja="すでに作成しているゾ")))


async def setup(bot: RT):
    await bot.add_cog(GlobalChat(bot))
