# RT - Log

from discord.ext import commands

from rtlib import RT, Cog, t


class RTLog(Cog):
    def __init__(self, bot: RT):
        self.bot = bot


class DiscordLog(Cog):
    def __init__(self, bot: RT):
        self.bot = bot


async def setup(bot):
    await bot.add_cog(RTLog(bot))
    await bot.add_cog(DiscordLog(bot))