# RT - Userinfo
from discord.ext import commands

from core import Cog


class Userinfo(Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.command()
    async def userinfo(self, ctx, *, id: int=None):
        user = await self.bot.search_user(id)
        Cog.Embed(title="")
 

async def setup(bot):
    await bot.add_cog(Userinfo(bot))
