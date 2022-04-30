# RT - Minesweeper

from discord.ext import commands
import discord

from core.cacher import Cacher
from core import Cog, RT, t

from rtutil.minesweeper import Minesweeper


class MinesweeperXYSelect(discord.ui.Select):
    "マインスイーパでX,Yを選択するためのSelectです。"

    def __init__(self, mode: str, max_: int):
        super().__init__(placeholder=mode, options=[
            discord.SelectOption(label=str(i), value=str(i))
            for i in range(max_)
        ])

    async def callback


class MinesweeperView(discord.ui.View):
    "マインスイーパーを操作するためのViewです。"

    def __init__(self, game: Minesweeper, mx: int, my: int, *args, **kwargs):
        assert mx <= 25 and my <= 25, {
            "ja": "でかすぎます。", "en": "It is so big that I can't make board."
        }
        self.game, self.mx, self.my = game, mx, my
        super().__init__(*args, **kwargs)
        self.add_item(make_select("x", mx))
        self.add_item(make_select("y", my))


class MinesweeperCog(Cog, name="Minesweeper"):
    def __init__(self, bot: RT):
        self.bot = bot
        self.games: Cacher[int, Minesweeper] = self.bot.cachers.acquire(180.0)

    @commands.command(aliases=("ms", "マインスイーパ", "マス"), fsparent="entertainment")
    @discord.app_commands.describe(mx="width", my="height", bomb="Number of mines")
    async def minesweeper(
        self, ctx: commands.Context, mx: int = 9, my: int = 9, bomb: int = 11
    ):
        self.games[ctx.author.id] = Minesweeper(mx, my, bomb)


async def setup(bot):
    await bot.add_cog(MinesweeperCog(bot))