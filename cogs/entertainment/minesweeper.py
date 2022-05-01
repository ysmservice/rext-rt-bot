# RT - Minesweeper

from __future__ import annotations

from discord.ext import commands
import discord

from core.cacher import Cacher
from core.views import TimeoutView
from core import Cog, RT, t

from rtutil.minesweeper import Minesweeper
from rtlib.common.utils import code_block


class MinesweeperXYSelect(discord.ui.Select):
    "マインスイーパでX,Yを選択するためのSelectです。"

    view: MinesweeperView

    def __init__(self, mode: str, max_: int):
        self.mode = mode
        super().__init__(placeholder=self.mode, options=[
            discord.SelectOption(label=str(i), value=str(i))
            for i in range(1, max_ + 1)
        ])

    async def callback(self, interaction: discord.Interaction):
        if self.view.selected[0] == "z":
            self.view.selected = (self.mode, int(self.values[0]))
            await interaction.response.defer()
        else:
            if self.mode == "y":
                result = self.view.game.set(
                    self.view.selected[1], int(self.values[0])
                )
            else:
                result = self.view.game.set(
                    int(self.values[0]), self.view.selected[1]
                )
            self.view.selected = ("z", 0)
            await interaction.response.edit_message(
                content=code_block(self.view.game.get(" "))
                    if result == 200
                    else "{}\n{}".format(
                        t({"ja": "あなたの負けです。", "en": "You lose"}, interaction)
                        if result == 410
                        else t(
                            {"ja": "あなたの勝ちです。", "en": "You won"},
                            interaction
                        ),
                        code_block(self.view.game.get_answer(" "))
                    )
            )


class MinesweeperView(TimeoutView):
    "マインスイーパーを操作するためのViewです。"

    def __init__(self, game: Minesweeper, mx: int, my: int, *args, **kwargs):
        assert mx <= 25 and my <= 25, {
            "ja": "でかすぎます。", "en": "It is so big that I can't make board."
        }
        self.game, self.mx, self.my = game, mx, my
        super().__init__(*args, **kwargs)
        self.add_item(MinesweeperXYSelect("x", mx))
        self.add_item(MinesweeperXYSelect("y", my))
        self.selected: tuple[str, int] = ("z", 0)


class MinesweeperCog(Cog, name="Minesweeper"):
    def __init__(self, bot: RT):
        self.bot = bot
        self.games: Cacher[int, Minesweeper] = self.bot.cachers.acquire(180.0)

    @commands.command(
        description="Minesweeper", aliases=("ms", "マインスイーパ", "マス"),
        fsparent="entertainment"
    )
    async def minesweeper(self, ctx: commands.Context):
        self.games[ctx.author.id] = Minesweeper(9, 9, 11)
        await ctx.reply(
            code_block(self.games[ctx.author.id].get(" ")), view=MinesweeperView(
                self.games[ctx.author.id], 9, 9
            )
        )

    (Cog.HelpCommand(minesweeper)
        .set_description(ja="マインスイーパを遊びます。", en="Play minesweeper")
        .update_headline(ja="マインスイーパ"))


async def setup(bot):
    await bot.add_cog(MinesweeperCog(bot))