# RT Music - Views

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias, TypeVar, Union, Any
from collections.abc import Callable, Coroutine, Iterator, Iterable

from asyncio import iscoroutine

import discord

from core import Cog, t
from core.utils import concat_text

from rtutil.views import EmbedPage, TimeoutView

from .utils import can_control, can_control_by_interaction, hundred_shorten

if TYPE_CHECKING:
    from .types_ import MusicRaw
    from .music import Music
    from .__init__ import MusicCog


ASK_EVERYONE = {
    "ja": "あなたはDJロールまたは権限を持っていないためこの操作を実行することができません。"
        "\nそこで、みんなに聞いてみたいと思います。",
    "en": "You do not have the DJ role or authority to perform this operation."
        "\nSo I would like to ask everyone."
}
AfterConfirm: TypeAlias = Union[Coroutine[Any, Any, str], Callable[[], str]]
class ConfirmView(TimeoutView):
    "確認ボタンを実装したViewです。"

    def __init__(
        self, after: AfterConfirm, required: int,
        *args: Any, **kwargs: Any
    ):
        kwargs.setdefault("timeout", 180.0)
        super().__init__(*args, **kwargs)
        self.after, self.required, self.ok = after, required, set()

    @staticmethod
    async def _run_after(after) -> str:
        return (await after) if iscoroutine(after) else after() # type: ignore

    @discord.ui.button(label="Okay", emoji="✅")
    async def confirm(self, interaction: discord.Interaction, _):
        self.ok.add(interaction.user)
        if len(self.ok) >= self.required:
            await interaction.response.send_message("{}\n{}".format(t(dict(
                ja="みんながOKしたので実効が決まりました。",
                en="Everyone said yes, so we decided to do the action."
            ), interaction), await self._run_after(self.after))) # type: ignore
        else:
            await interaction.response.send_message("Ok", ephemeral=True)
        self.set_message(interaction)

    @classmethod
    async def process(
        cls, ctx: Cog.Context, content: dict[str, str],
        dj_role_id: int | None, after: AfterConfirm
    ) -> None:
        "渡されたコルーチンを実行します。また、他の人への確認が必要無場合は確認を行います。"
        assert isinstance(ctx.author, discord.Member) and ctx.author.voice is not None \
            and ctx.author.voice.channel is not None
        if can_control(ctx.author, dj_role_id):
            await ctx.reply(await cls._run_after(after))
        else:
            view = cls(after, len(ctx.author.voice.channel.members))
            view.set_message(ctx, await ctx.reply(
                t(concat_text(content, ASK_EVERYONE), ctx), view=view
            ))


SpT = TypeVar("SpT")
def _extract_per_sample(musics: Iterable[SpT], sample: int = 15) -> Iterator[list[SpT]]:
    # リストから
    stack, length = [], 0
    for music in musics:
        stack.append(music)
        length += 1
        if length == sample:
            yield stack
            stack, length = [], 0
    if stack:
        yield stack


class MusicListView(EmbedPage):
    "音楽のページリストを作るためのViewです。"

    def __init__(
        self, cog: MusicCog, title: str,
        musics: Iterable[MusicRaw | Music],
        *args: Any, **kwargs: Any
    ):
        self.musics = list(_extract_per_sample(musics))
        self.title, self.cog = title, cog
        super().__init__([], *args, **kwargs)
        self.update_embeds()

    def make_option_text(self, music: Music | MusicRaw) -> str:
        return f"[{music['title']}]({music['url']})"

    def update_embeds(self) -> None:
        "埋め込みを最新の状態にします。"
        self.embeds = [
            Cog.Embed(self.title, description="\n".join(
                self.make_option_text(music) for music in sample
            )) for sample in self.musics
        ]


class MusicListWithSelectView(MusicListView):
    "`MusicListView`を拡張してセレクトボタンを簡単に実装できるようにしたViewです。"

    selects: dict[str, dict[str, str]] = {}

    def __init__(self, ctx: Any, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.ctx = ctx
        self.mapped_selects = {
            value.custom_id: value for value in self.children
            if isinstance(value, discord.ui.Select)
        }
        for key, text in self.selects.items():
            self.mapped_selects[key].placeholder = t(text, ctx)
        self.update_options()

    @staticmethod
    def select(*args: Any, **kwargs: Any) -> ...:
        "Select用のデコレータを返します。"
        return discord.ui.select(*args, placeholder="...", **kwargs)

    def remove_options(self, values: Iterable[str]):
        "渡されたイテラブルのオブジェクトが返す文字列(インデックス番号)にあるオプションを消します。"
        for index in sorted(map(int, values), reverse=True):
            if self.page == 1 and index == 0:
                continue
            del self.musics[self.page][index]

    def update_options(self) -> None:
        "セレクトのオプションを更新します。"
        for item in self.mapped_selects.values():
            if item.custom_id in self.selects:
                item.options.clear()
                for index, music in enumerate(self.musics[self.page]):
                    item.add_option(
                        label=hundred_shorten(music["title"]),
                        value=str(index), description=hundred_shorten(music["url"])
                    )

    async def update(self, interaction: discord.Interaction) -> None:
        "セレクトの内容の更新をして埋め込みの更新をし返信をします。"
        self.update_options()
        self.update_embeds()
        await interaction.response.edit_message(embed=self.embeds[self.page], view=self)


class QueueListView(MusicListWithSelectView):
    "キューを閲覧/管理するためのViewです。"

    selects = {
        "music.remove_queue": {
            "ja": "キューから曲を削除",
            "en": "Remove music from the queue"
        }
    }

    def make_option_text(self, music: Music) -> str:
        return f"{music.author.mention}：[{music['title']}]({music['url']})"

    def _remove_options(self, select: discord.ui.Select) -> str:
        self.remove_options(select.values)
        return t(dict(
            ja="キューから曲を削除しました。",
            en="Song removed from queue."
        ), self.ctx.guild.id)

    @MusicListWithSelectView.select(custom_id="music.remove_queue")
    async def remove_queue(self, interaction: discord.Interaction, select: discord.ui.Select):
        assert isinstance(interaction.user, discord.Member)
        if await can_control_by_interaction(interaction, self.cog):
            await interaction.response.edit_message(
                content=self._remove_options(select),
                embed=None, view=None
            )
        elif interaction.user.voice is None:
            await interaction.response.send_message(t(dict(
                ja="音楽を聴いてない人がキューから曲を削除することはできません。",
                en="People who are not listening to music cannot delete songs from the queue."
            ), interaction.user), ephemeral=True)
        else:
            await interaction.response.edit_message(
                content=concat_text(
                    ASK_EVERYONE, {
                        "ja": "キューを何曲か削除しても良いですか？",
                        "en": "Can I delete some songs from the queue?"
                    }, "\n"
                ), view=ConfirmView(
                    lambda: self._remove_options(select),
                    len(interaction.user.voice.channel.members) # type: ignore
                )
            )
            self.set_message(interaction)