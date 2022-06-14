# RT - blocker

from discord.ext import commands

from core import Cog, t, Embed

from .__init__ import FSPARENT

class Blocker(Cog):
    def __init__(self, bot):
        self.bot = bot

    

async def setup(bot):
    await bot.add_cog(Blocker(bot))
