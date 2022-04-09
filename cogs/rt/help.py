# RT - Help

from inspect import cleandoc

from discord.ext import commands
from discord import app_commands

from rtlib import RT, Cog


class Help(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data: dict[str, dict[str, Cog.Help]] = {}

    @commands.Cog.listener()
    async def on_ready(self):
        ...

    def load(self):
        "Load help"
        for command in self.bot.walk_commands():
            category = getattr(command.cog, "__category__", None)
            if category is not None:
                value = getattr(command, f"HELP_{command.name.upper()}", None)
                if value is not None:
                    self.data[category] = value

    @commands.command(
        aliases=("h", "ヘルプ", "助けて", "へ", "HelpMe,RITSUUUUUU!!"),
        description="Displays how to use RT."
    )
    async def help(self, ctx: commands.Context, *, word: str) -> None:
        await ctx.reply()

    Cog.Help(help) \
        .add_arg("word", "str", ja="検索ワードまたはコマンド名", en="Search word or command name") \
        .set_description(ja="ヘルプコマンドです。")


async def setup(bot):
    await bot.add_cog(Help(bot))