# RT - nsfw
from discord.ext import commands
from discord import app_commands
import discord

from core import Cog, t


class Nsfw(Cog):
    def __init__(self, bot):
        self.bot = bot
    
    
    @commands.command(
        description="Setting nsfw channel",
        ailias=("えっc", "r18")
    )
    @app_commands.describe(channel="Text channel")
    async def nsfw(self, ctx, channel: discord.TextChannel=None):
        pass
    
    Cog.HelpCommand(nsfw) \
        .set_description(ja="nsfwチャンネルに設定します。", en="Setting nsfw channel") \
        .merge_headline(ja="nsfwチャンネルを設定します。") \
        .add_arg("channel", "Optional", ja="設定したいテキストチャンネル",
                 en="When you want to setting nsfw channel")
    
    
async def setup(bot):
    await bot.add_cog(Nsfw(bot))
