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
    @app_commands.describe(channel="Text channel", nsfw="If you want to set nsfw, you should to do true")
    async def nsfw(self, ctx, nsfw: bool, channel: discord.TextChannel=None):
        ch = channel or ctx.channel
        await ch.edit(nsfw=nsfw)
        await ctx.send(t({"ja": f"{ch.mention}を設定しました", "en": "Setting nsfw"}))
    
    Cog.HelpCommand(nsfw) \
        .set_description(ja="nsfwチャンネルに設定します。", en="Setting nsfw channel") \
        .merge_headline(ja="nsfwチャンネルを設定します。") \
        .add_arg("channel", "Optional", ja="設定したいテキストチャンネル",
                 en="When you want to setting nsfw channel")
    
    
async def setup(bot):
    await bot.add_cog(Nsfw(bot))
