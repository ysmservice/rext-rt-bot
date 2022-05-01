# RT - Entertainment

import discord
from discord import app_commands
from discord.ext import commands

from aiohttp import ClientSession

from core import RT, Cog, HelpCommand, t

from rtutil.minecraft import search, NotFound


class Entertainment(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
    
    async def cog_load(self):
        self.session: ClientSession = ClientSession()
        
    @commands.command(description="Search minecraft user")
    @app_commands.describe(user="Minecraft user name")
    async def minecraft(self, ctx, *, user: str):
        try:
            result = await search(self.session, user)
        except NotFound:
            await ctx.send(t(ja="そのユーザーは見つかりません", en="I can't found that user"), ctx)
        else:
            embed = discord.Embed(title=result.name)
            embed.add_field(name="UUID", value=result.id)
            embed.set_image(url=result.skin)
            await ctx.send(embed=embed)
            
    HelpCommand(minecraft) \
        .set_description(ja="マイクラユーザー検索", en="minecraft user search)
        .add_arg("user", "str", None,
                 ja="マイクラのユーザ名", en="Minecraft user name")
        .update_headline(ja="マイクラのユーザー検索をします")
            

async def setup(bot: RT):
    await bot.add_cog(MinecraftSearch(bot))
