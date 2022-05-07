# RT - Token Remover

from re import findall

from discord.ext import commands
import discord

from core import RT, Cog, t

from rtlib.common.cacher import Cacher


def check_token(content: str) -> bool:
    "TOKENが含まれているか確認します。"
    return bool(findall(r"[A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}", content))


class TokenRemoverEventContext(Cog.EventContext):
    author: discord.Member


class TokenRemover(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.caches: Cacher[discord.Member, int] = self.bot.cachers.acquire(3600.0)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or not message.content \
                or not isinstance(message.author, discord.Member):
            return

        if check_token(message.content):
            if message.author not in self.caches:
                self.caches[message.author] = 0
            if self.caches[message.author] < 10:
                self.caches[message.author] += 1
                if self.caches[message.author] == 5:
                    await message.reply(t(dict(
                        ja="TOKENなるものを送らないでください。",
                        en="Please do not send anything that is TOKEN."
                    ), message.author))
                elif self.caches[message.author] == 8:
                    ctx = TokenRemoverEventContext(
                        self.bot, message.guild, "SUCCESS", {
                            "ja": "Token削除", "en": "Token Spam Remover"
                        }, feature=("TokenRemover", "server-safety")
                    )
                    try:
                        await message.author.ban(reason=t(dict(
                            ja="TOKENと思われるもの8回は送ったため。",
                            en="For sending what appears to be TOKEN 8 times."
                        ), message.guild))
                    except discord.Forbidden:
                        ctx.detail = t(self.FORBIDDEN, message.guild)
                        ctx.status = "ERROR"
                    self.bot.rtevent.dispatch("on_token_remove", ctx)


async def setup(bot):
    await bot.add_cog(TokenRemover(bot))