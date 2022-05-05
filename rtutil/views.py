# RT - Views

from typing import TypeAlias, Literal, Optional
from collections.abc import Sequence, Callable, Iterator

from functools import cache

from discord.ext.commands import Context as OriginalContext
import discord

from discord.ext.fslash import Context

from core.types_ import Text
from core.utils import separate
from core import t


__all__ = (
    "TimeoutView", "PageMode", "BasePage", "EmbedPage", "NoEditEmbedPage",
    "separate_to_embeds", "check", "CANT_MODE"
)
CANT_MODE = dict(
    ja="これ以上ページを捲ることができません。",
    en="I can't turn the page any further."
)


class TimeoutView(discord.ui.View):
    "タイムアウト時にコンポーネントを使用不可に編集するようにするViewです。"

    target: discord.abc.Snowflake | int
    ctx: Optional[discord.Message | discord.Interaction] = None

    async def on_timeout(self):
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True # type: ignore
        if self.ctx is not None:
            if isinstance(self.ctx, discord.Message):
                await self.ctx.edit(view=self)
            else:
                await self.ctx.edit_original_message(view=self)

    def set_message(
        self, ctx: Context | OriginalContext | discord.Interaction,
        message: Optional[discord.Message] = None
    ):
        "Viewを編集するメッセージを指定します。"
        if isinstance(ctx, Context):
            self.ctx = ctx.interaction
        elif message is not None:
            self.ctx = message
        elif isinstance(ctx, discord.Interaction):
            self.ctx = ctx


async def check(
    view: discord.ui.View, interaction: discord.Interaction
) -> bool:
    """ユーザーがViewを使用することができるかどうかを確認します。
    これを使用する場合は`view`に、対象のユーザーIDまたはオブジェクトが入った`target`を付けておく必要があります。"""
    assert isinstance(interaction, discord.Interaction), "インタラクションオブジェクトじゃないものが渡されました。"
    if interaction.user.id == getattr(getattr(view, "target"), "id", getattr(view, "target")):
        return True
    await interaction.response.send_message(t(dict(
        ja="あなたはこのコンポーネントを使うことができません。",
        en="You can't use this component."
    ), interaction), ephemeral=True)
    return False


PageMode: TypeAlias = Literal["dl", "l", "r", "dr"]
class BasePage(TimeoutView):

    lock = False
    page = 0
    enable_lock = False

    def update_counter(self):
        self.counter.label = str(self.page + 1)

    async def cant_more(self, interaction: discord.Interaction):
        "これ以上進めないことをユーザーに伝えます。"
        await interaction.response.send_message(t(CANT_MODE, interaction), ephemeral=True)

    async def on_turn(
        self, mode: PageMode, interaction: discord.Interaction
    ) -> bool:
        if mode[-1] == "r" and self.lock and self.enable_lock:
            await self.cant_more(interaction)
            return True
        else:
            if self.lock: self.lock = False
            self.page = self.page + \
                (-1 if mode.endswith("l") else 1)*((mode[0] == "d")+1)
            if self.page == -1:
                await self.cant_more(interaction)
                self.page = 0
                return True
            else:
                self.update_counter()
        return False

    @discord.ui.button(emoji="⏪", custom_id="BPViewDashLeft")
    async def dash_left(self, interaction: discord.Interaction, _):
        await self.on_turn("dl", interaction)

    @discord.ui.button(emoji="◀️", custom_id="BPViewLeft")
    async def left(self, interaction: discord.Interaction, _):
        await self.on_turn("l", interaction)

    @discord.ui.button(label="1", custom_id="BPViewCounter")
    async def counter(self, interaction: discord.Interaction, _):
        await interaction.response.send_message(t(dict(
                ja="へんじがない。ただの　しかばね　のようだ。", en="Kara Kara Kara no Kara"
        ), interaction), ephemeral=True)

    @discord.ui.button(emoji="▶️", custom_id="BPViewRight")
    async def right(self, interaction: discord.Interaction, _):
        await self.on_turn("r", interaction)

    @discord.ui.button(emoji="⏩", custom_id="BPViewDashRight")
    async def dash_right(self, interaction: discord.Interaction, _):
        await self.on_turn("dr", interaction)


def separate_to_embeds(
    description: str, on_make: Callable[[str], discord.Embed]
        = lambda text: discord.Embed(description=text),
    extractor: Callable[[str], str] = lambda text: text[:2000]
) -> Iterator[discord.Embed]:
    "渡された説明で`on_make`を呼び出して、説明を複数の埋め込みに分割します。"
    for text in separate(description, extractor):
        yield on_make(text)


class EmbedPage(BasePage):
    "埋め込みのページメニューです。"

    def __init__(self, embeds: Sequence[discord.Embed], *args, select: bool = False, **kwargs):
        self.embeds = embeds
        super().__init__(*args, **kwargs)
        if select:
            self.select = discord.ui.Select()
            self.select.callback = self.on_select
            for i in range(1, len(embeds)+1):
                self.select.add_option(label=f"{i} Page", value=str(i))
            self.add_item(self.select)

    @cache
    def get_length(self) -> int:
        return len(self.embeds)

    async def on_select(self, interaction: discord.Interaction):
        self.page = int(self.select.values[0])
        self.update_counter()
        await interaction.response.edit_message(
            embed=self.embeds[self.page], **self.on_edit(
                interaction, view=self
            )
        )

    async def on_turn(self, mode: PageMode, interaction: discord.Interaction) -> bool:
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
                await self.cant_more(interaction)
                return True
        self.update_counter()
        await interaction.response.edit_message(
            embed=embed, **self.on_edit(interaction, view=self)
        )
        return True

    def on_edit(self, _: discord.Interaction, **kwargs):
        return kwargs

    async def first_reply(
        self, ctx: Context | OriginalContext, if_none: Text = dict(
            ja="何もありません。", en="Nothing."
        )
    ) -> None:
        "一番最初の返信をします。"
        if len(self.embeds) > 1:
            self.set_message(ctx, await ctx.reply(embed=self.embeds[0], view=self)) # type: ignore
        elif self.embeds:
            await ctx.reply(embed=self.embeds[0])
        else:
            await ctx.reply(t(if_none, ctx))


class NoEditEmbedPage(EmbedPage):
    "ページ切り替え時にViewを更新しないようにした`EmbedPage`です。"

    def on_edit(self, _, **kwargs):
        del kwargs["view"]
        return kwargs