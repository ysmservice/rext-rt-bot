# RT - Views

from typing import Literal, TypeAlias, Optional
from collections.abc import Callable

import discord

from .__init__ import t


__all__ = ("TimeoutView", "Mode", "BasePage", "EmbedPage", "prepare_embeds")


class TimeoutView(discord.ui.View):
    "タイムアウト時にコンポーネントを使用不可に編集するようにするViewです。"

    message: discord.Message

    async def on_timeout(self):
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True # type: ignore
        await self.message.edit(view=self)


Mode: TypeAlias = Literal["dl", "l", "r", "dr"]
class BasePage(TimeoutView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.page = 0
        self.counter.label = str(self.page)

    async def on_turn(
        self, mode: Mode, _: discord.Interaction
    ):
        self.page = self.page + \
            (-1 if mode.endswith("l") else 1)*((mode[0] == "d")+1)
        self.counter.label = str(self.page)

    @discord.ui.button(emoji="⏪")
    async def dash_left(self, interaction: discord.Interaction, _):
        await self.on_turn("dl", interaction)

    @discord.ui.button(emoji="◀️")
    async def left(self, interaction: discord.Interaction, _):
        await self.on_turn("l", interaction)

    @discord.ui.button(custom_id="BPViewCounter")
    async def counter(self, interaction: discord.Interaction, _):
        await interaction.response.send_message("へんじがない。ただの　しかばね　のようだ。")

    @discord.ui.button(emoji="▶️")
    async def right(self, interaction: discord.Interaction, _):
        await self.on_turn("r", interaction)

    @discord.ui.button(emoji="⏩")
    async def dash_right(self, interaction: discord.Interaction, _):
        await self.on_turn("dr", interaction)


def prepare_embeds(
    description: str, on_make: Callable[[str], discord.Embed]
        = lambda text: discord.Embed(description=text),
    set_page: Optional[Callable[[discord.Embed, int, int], None]] = None
) -> list[discord.Embed]:
    "Split description into list of embed."
    embeds: list[discord.Embed] = []
    while description:
        embeds.append(on_make(description[:2000]))
        description = description[2000:]
    if set_page is not None:
        length = len(embeds)
        for i in range(len(embeds)):
            set_page(embeds[i], i+1, length)
    return embeds


class EmbedPage(BasePage):
    "埋め込みのページメニューです。"

    prepare_embeds = staticmethod(prepare_embeds)

    def __init__(self, embeds: list[discord.Embed], *args, select: bool = False, **kwargs):
        self.embeds = embeds
        super().__init__(*args, **kwargs)
        if select:
            self.select = discord.ui.Select()
            self.select.callback = self.on_select
            for i in range(len(embeds)):
                self.select.add_option(label=f"{i}ページ目", value=str(i))
            self.add_item(self.select)

    async def on_select(self, interaction: discord.Interaction):
        self.page = int(self.select.values[0])
        self.counter.label = self.select.values[0]
        await interaction.response.edit_message(
            embed=self.embeds[self.page], **self.on_page(
                interaction
            )
        )

    async def on_turn(self, mode: Mode, interaction: discord.Interaction):
        before = self.page
        await super().on_turn(mode, interaction)
        try:
            assert 0 <= self.page
            embed = self.embeds[self.page]
        except (AssertionError, IndexError):
            self.page = before
            if mode == "dl":
                self.page = 0
                embed = self.embeds[self.page]
            elif mode == "dr":
                self.page = len(self.embeds) - 1
                embed = self.embeds[self.page]
            else:
                return await interaction.response.send_message(t(dict(
                    ja="これ以上ページを捲ることができません。",
                    en="I can't turn the page any further."
                ), interaction), ephemeral=True)
        await interaction.response.edit_message(embed=embed, **self.on_page(interaction))

    def on_page(self, _: discord.Interaction):
        return {}