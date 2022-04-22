# RT - Translator

import discord

from jishaku.functools import executor_function
from deep_translator import GoogleTranslator

from rtlib import Cog


class Translator(Cog):
    def __init__(self, bot):
        self.bot = bot
     
    @executor_function
    def translate(self,
                  source: str,
                  target: str,
                  content: str):
        return GoogleTranslator(source=source, target=target).translate(content)
        
    @Cog.listener()
    async def on_message(self, message: discord.Message):
        for line in message.channel.topic.splitlines:
            if line.startswith("rt<tran "):
                _, source, target = line.split()
                translated = await self.translate(source, target, message.content)
                embed = discord.Embed(title="translate", description=translated)
                await message.channel.send(embed=embed)
                
                
                break
                
async def setup(bot):
    await bot.add_cog(Translator(bot))
