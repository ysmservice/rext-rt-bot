# RT - Views

from __future__ import annotations

from typing import TypeAlias, Literal, Optional
from collections.abc import Sequence, Callable, Iterator

from functools import cache

from discord.ext.commands import Context as OriginalContext
import discord

from discord.ext.fslash import Context

from core.types_ import Text, UserMember
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

    target: discord.abc.Snowflake | int | UserMember
    _ctx: Optional[discord.Message | discord.Interaction | OriginalContext] = None

    async def on_timeout(self):
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True # type: ignore
        if self._ctx is not None:
            if hasattr(self._ctx, "edit"):
                await self._ctx.edit(view=None) # type: ignore
            elif isinstance(self._ctx, discord.Interaction):
                await self._ctx.edit_original_message(view=None)

    def set_message(
        self, ctx: Context | OriginalContext | discord.Interaction | None,
        message: Optional[discord.Message | OriginalContext | Context] = None
    ):
        "Viewを編集するメッセージを指定します。"
        if isinstance(ctx, Context):
            self._ctx = ctx.interaction
        elif isinstance(ctx, discord.Interaction):
            self._ctx = ctx
        if isinstance(message, OriginalContext | discord.Message):
            self._ctx = message


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


class ChangePageModal(discord.ui.Modal):
    "BasePageのページ入力のモーダルです。"

    page = discord.ui.TextInput(label="Page")

    def __init__(self, from_: BasePage, *args, **kwargs):
        self.from_ = from_
        super().__init__(*args, **kwargs)

    async def on_submit(self, interaction: discord.Interaction):
        self.from_.page = int(str(self.page)) - 1
        self.from_.update_counter()
        await self.from_.on_turn("change", interaction)


PageMode: TypeAlias = Literal["dl", "l", "r", "dr", "change"]
class BasePage(TimeoutView):

    lock = False
    page = 0
    enable_lock = False

    def update_counter(self):
        self.counter.label = str(self.page + 1)

    async def cant_more(self, interaction: discord.Interaction):
        # await interaction.response.send_message(t(CANT_MODE, interaction), ephemeral=True)
        await interaction.response.defer()

    async def on_turn(self, mode: PageMode, _: discord.Interaction) -> None:
        if mode == "change" or (self.lock and self.enable_lock and mode[-1] == "r"):
            return
        self.page = self.page + \
            (-1 if mode.endswith("l") else 1)*((mode[0] == "d")+1)
        self.update_counter()

    def get_length(self) -> int:
        return 0

    @discord.ui.button(emoji="⏪", custom_id="BPViewDashLeft")
    async def dash_left(self, interaction: discord.Interaction, _):
        await self.on_turn("dl", interaction)

    @discord.ui.button(emoji="◀️", custom_id="BPViewLeft")
    async def left(self, interaction: discord.Interaction, _):
        await self.on_turn("l", interaction)

    @discord.ui.button(label="1", custom_id="BPViewCounter", style=discord.ButtonStyle.blurple)
    async def counter(self, interaction: discord.Interaction, _):
        if self.enable_lock:
            return await interaction.response.defer()
        await interaction.response.send_modal(ChangePageModal(self, title=t({
            "ja": "ページ指定移動", "en": "Change page directly"
        }, interaction)))

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
            # これ以上いけない場合は一番最初か最後にする。
            match mode[-1]:
                case "l":
                    self.page = 0
                case "r":
                    self.page = len(self.embeds) - 1
                case _:
                    self.page = before
            embed = self.embeds[self.page]
            self.update_counter()
        kwargs = dict(embed=embed, **self.on_edit(interaction, view=self))
        await interaction.response.edit_message(**kwargs)
        return False

    def on_edit(self, _: discord.Interaction, **kwargs):
        return kwargs

    async def first_reply(
        self, ctx: Context | OriginalContext | discord.abc.Messageable,
        if_none: Text = dict(ja="何もありません。", en="Nothing."), **kwargs
    ) -> None:
        "一番最初の返信をします。"
        reply = isinstance(ctx, Context | OriginalContext | discord.Message)
        if len(self.embeds) > 1:
            kwargs.update(embed=self.embeds[0], view=self) # type: ignore
            if reply:
                self.set_message(ctx, await ctx.reply(**kwargs))
            else:
                self.set_message(None, await ctx.send(**kwargs))
        elif self.embeds:
            kwargs.update(embed=self.embeds[0])
            if reply:
                await ctx.reply(**kwargs)
            else:
                await ctx.send(**kwargs)
        else:
            kwargs.update(content=t(if_none, ctx))
            if reply:
                await ctx.reply(**kwargs)
            else:
                await ctx.send(**kwargs)


class NoEditEmbedPage(EmbedPage):
    "ページ切り替え時にViewを更新しないようにした`EmbedPage`です。"

    def on_edit(self, _, **kwargs):
        del kwargs["view"]
        return kwargs