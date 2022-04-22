# RT - Reprypt

from discord.ext import commands
import discord

from jishaku.functools import executor_function
from reprypt import encrypt, decrypt

from rtlib.utils import code_block
from rtlib import Cog, RT


class Reprypt(Cog):
    def __init__(self, bot: RT):
        self.bot = bot

    @executor_function
    def process(self, mode: str, text: str, key: str) -> str:
        return encrypt(text, key) if mode == "en" else decrypt(text, key)

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

    @reprypt_.command(aliases=("en", "暗号化"))
    @discord.app_commands.describe(
        key="The password required for decryption.",
        content="The text to be encrypted."
    )
    async def encrypt(self, ctx, key: str, *, content: str):
        await ctx.reply(
            code_block(await self.process("en", key, content)),
            allowed_mentions=discord.AllowedMentions.none()
        )

    @reprypt_.command(aliases=("de", "復号化"))
    @discord.app_commands.describe(
        key="The password used for encryption.",
        content="The encrypted text to be decrypted."
    )
    async def decrypt(self, ctx, key: str, *, content: str):
        await ctx.reply(
            code_block(await self.process("de", key, content)),
            allowed_mentions=discord.AllowedMentions.none()
        )
    
    (Cog.HelpCommand(reprypt_) 
        .set_description(ja="Repryptを使用して文章を暗号化/復号化します。", en="Encryption/Decryption by Reprypt.") \
        .update_headline(ja="Repryptを使用して文章を暗号化/復号化します。")
        .add_sub(Cog.HelpCommand(encrypt)
            .set_description(ja="指定された文章を暗号化します。", en="Encrypts the specified text.")
            .add_arg("key", "str", ja="復号時に必要となるパスワードです。",
                en="The password required for decryption.")
            .add_arg("content", "str", ja="暗号化する文章です。",
                en="The text to be encrypted."))
        .add_sub(Cog.HelpCommand(decrypt)
            .set_description(ja="Repryptで暗号化された文章を復号化します。", en="Decrypts the text encrypted by Reprypt.")
            .add_arg("key", "str", ja="暗号化する時に使ったパスワードです。",
                en="The password used for encryption.")
            .add_arg("content", "str", ja="復号したい暗号化された文章です。",
                en="The encrypted text to be decrypted.")
        ))


async def setup(bot):
    await bot.add_cog(Reprypt(bot))