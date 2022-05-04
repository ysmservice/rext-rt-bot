# RT - Short URL

from discord.ext import commands
import discord

from core import RT, Cog

from rtlib.common.short_url import ShortURLManager

from .__init__ import FSPARENT


class ShortURL(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = ShortURLManager(self.bot.pool)

    @commands.command(
        aliases=("surl", "短縮", "短縮URL"), fsparent=FSPARENT,
        description="Shorten the URL."
    )
    @commands.cooldown(1, 10, commands.BucketType.user)
    @discord.app_commands.describe(
        endpoint=(endpoint_d := "This is the string that comes at the end of the URL."),
        url=(url_d := "URL to shorten.")
    )
    async def short(self, ctx: commands.Context, endpoint: str, *, url: str):
        await ctx.typing()
        await self.data.register(ctx.author.id, url, endpoint)
        await ctx.reply(
            f"Ok: http://rtbo.tk/{endpoint}", allowed_mentions=discord.AllowedMentions.none()
        )

    (Cog.HelpCommand(short)
        .merge_headline(ja="URLを短縮します。")
        .set_description(
            ja="URLを短縮します。",
            en=short.description
        )
        .add_arg("endpoint", "str",
            ja="短縮後のURLの最後にくる文字列です。",
            en=endpoint_d)
        .add_arg("url", "str",
            ja="短縮するURLです。", en=url_d))
    del endpoint_d, url_d


async def setup(bot):
    await bot.add_cog(ShortURL(bot))