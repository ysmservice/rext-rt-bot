# RT - blocker

from discord.ext import commands

from core import Cog, t, Embed, DataBaseManager, cursor

from .__init__ import FSPARENT


class DataManager(DataBaseManager):
    def __init__(self, bot):
        self.bot = bot

    async def prepare_table(self):
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS Blocker(
                GuildId BIGINT PRIMARY KEY NOT NULL, EmojiBlock BOOLEAN, StampBlock BOOLEAN, Exceptions JSON
            );""")


class Blocker(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = DataManager(bot)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.command(description="Setting blocker")
    async def blocker(self, ctx):
        pass


async def setup(bot):
    await bot.add_cog(Blocker(bot))
