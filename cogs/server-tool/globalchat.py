# RT - server-tool global
import discord
from discord.ext import commands

from core import Cog, RT, t, DatabaseManager, cursor


class DataManager(DatabaseManager):
    def __init__(self, bot: RT):
        self.pool = bot.pool
    
    async def create_chat(self, name: str, channel: discord.TextChannel):
        await cursor.execute(
            "INSERT INTO GlobalChat VALUES(%s, %s);",
            (name, channel.id)
        )
        
    async def prepare_table(self):
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalChat(
                name TEXT, channelid BIGINT
            );"""
        )


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
            await ctx.send(t(ctx, dict(en="Invaild command", ja="使い方が間違っているゾ")))
            
    @globalchat.command(
        description="Create globalchat",
        aliases=("make", "add")
    )
    async def create(self, ctx, name: str = None):
        pass
    

async def setup(bot: RT):
    await bot.add_cog(GlobalChat(bot))
