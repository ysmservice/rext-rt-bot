# RT - Individual

from discord.ext import commands
import discord

from core import RT, Cog

from rtutil.collectors import make_google_url


FSPARENT = "individual"


class Individual(Cog):
    def __init__(self, bot: RT):
        self.bot = bot

    @commands.command(
        aliases=("google", "グーグル", "ggrks", "gg"), fsparent=FSPARENT,
        description="Create a search URL in Google."
    )
    @discord.app_commands.describe(query="Query for searching.")
    async def search(self, ctx: commands.Context, *, query: str):
        await ctx.reply(
            f"URL: {make_google_url(query)}",
            allowed_mentions=discord.AllowedMentions.none()
        )

    (Cog.HelpCommand(search)
        .merge_headline(ja="Googleの検索URLを作ります。")
        .set_description(ja="Googleの検索URLを作ります。", en=search.description)
        .add_arg("query", "str",
            ja="検索ワードです。", en="The word that you want to search."))


async def setup(bot):
    await bot.add_cog(Individual(bot))