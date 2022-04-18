# RT - Reprypt

from discord.ext import commands
from rtlib import Cog
import discord

from time import time
import reprypt


class Reprypt(Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(
        extras={
            "headding": {"ja": "Repryptを使用して文章を暗号化/復号化します。",
                         "en": "..."},
            "parent": "Individual"
        },
        name="reprypt"
    )
    async def reprypt_(self, ctx):
        """!lang ja
        --------
        Repryptを使用して文章を暗号化/復号化します。
        !lang en
        --------
        Encryption/Decryption by Reprypt."""
        if not ctx.invoked_subcommand:
            await ctx.reply(
                {"ja": "使い方が違います。",
                 "en": "..."}
            )

    @reprypt_.command(aliases=["en"])
    async def encrypt(self, ctx, key, *, content):
        """!lang ja
        --------
        指定された文章を暗号化します。
        Parameters
        ----------
        key : str
            復号時に必要となるパスワードです。
        content : str
            暗号化する文章です。
        Examples
        --------
        `rt!reprypt encrypt tasuren 私の極秘情報！`
        Aliases
        -------
        en
        !lang en
        --------
        
        Encrypts the specified text.
        Parameters
        ----------
        key : str
            The password required for decryption.
        content : str
            The text to be encrypted.
        Examples
        --------
        `rt!reprypt encrypt tasuren My top secret!`
        Aliases
        -------
        en
        """
        result = reprypt.encrypt(content, key)
        await ctx.reply(
            f"```\n{result}\n```", replace_language=False,
            allowed_mentions=discord.AllowedMentions.none()
        )

    @reprypt_.command(aliases=["de"])
    async def decrypt(self, ctx, key, *, content):
        """!lang ja
        --------
        Repryptで暗号化された文章を復号化します。
        Parameters
        ----------
        key : str
            暗号化する時に使ったパスワードです。
        content : str
            復号したい暗号化された文章です。
        Aliases
        -------
        de
        Examples
        --------
        `rt!reprypt encrypt tasuren ByGqa44We55B1u56e5oYO65FC77x`
        !lang en
        --------
        Decrypts the text encrypted by Reprypt.
        Parameters
        ----------
        key : str
            The password used for encryption.
        content : str
            The encrypted text to be decrypted.
        Aliases
        -------
        de
        Examples
        --------
        `rt!reprypt encrypt tasuren ByGqa44We55B1u56e5oYO65FC77x`
        """
        result = reprypt.decrypt(content, key)
        await ctx.reply(
            f"```\n{result}\n```", replace_language=False,
            allowed_mentions=discord.AllowedMentions.none()
        )


async def setup(bot):
    await bot.add_cog(Reprypt(bot))
