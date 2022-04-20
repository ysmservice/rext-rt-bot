# RT - Reprypt

from time import time
from discord.ext import commands
from discord import app_commands
import discord
from rtlib import Cog, RT
import reprypt


class Reprypt(Cog):
    def __init__(self, bot: RT):
        self.bot = bot

    @commands.group(
        name="reprypt",
        description="Use Reprypt to encrypt/decrypt sentences."
    )
    async def reprypt_(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.reply(
                {"ja": "使い方が違います。",
                 "en": "The usage is different."}
            )

    @reprypt_.command(aliases=("en"))
    @app_commands.describe(key="The password required for decryption.",
                           content="The text to be encrypted.")
    async def encrypt(self, ctx, key: str, *, content: str):
        result = reprypt.encrypt(content, key)
        await ctx.reply(
            f"```\n{result}\n```", allowed_mentions=discord.AllowedMentions.none()
        )

    @reprypt_.command(aliases=("de"))
    @app_commands.describe(key="The password used for encryption.", content="The encrypted text to be decrypted.")
    async def decrypt(self, ctx, key: str, *, content: str):
        result = reprypt.decrypt(content, key)
        await ctx.reply(
            f"```\n{result}\n```", replace_language=False,
            allowed_mentions=discord.AllowedMentions.none()
        )
    
    Cog.HelpCommand(reprypt_) \
        .set_description(ja="Repryptを使用して文章を暗号化/復号化します。", en="Encryption/Decryption by Reprypt.") \
        .update_headline(ja="Repryptを使用して文章を暗号化/復号化します。") \
        .add_sub(Cog.HelpCommand(encrypt)
                    .set_description(ja="指定された文章を暗号化します。", en="Encrypts the specified text.")
                    .add_args("key", "str", ja="復号時に必要となるパスワードです。",
                              en="The password required for decryption.")
                    .add_args("content", "str", ja="暗号化する文章です。",
                              en="The text to be encrypted.")
                )
        .add_sub(Cog.HelpCommand(decrypt)
                    .set_description(ja="Repryptで暗号化された文章を復号化します。", en="Decrypts the text encrypted by Reprypt.")
                    .add_args("key", "str", ja="暗号化する時に使ったパスワードです。",
                              en="The password used for encryption.")
                    .add_args("content", "str", ja="復号したい暗号化された文章です。",
                              en="The encrypted text to be decrypted.")
                )


async def setup(bot):
    await bot.add_cog(Reprypt(bot))
