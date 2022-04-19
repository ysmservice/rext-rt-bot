# RT - Help

from __future__ import annotations

from typing import NamedTuple, Literal, Optional, Any
from collections.abc import Sequence

from collections import defaultdict
from inspect import getfile

from discord.ext import commands
import discord

from rtlib.views import TimeoutView, EmbedPage, NoEditEmbedPage, check, separate_to_embeds
from rtlib.utils import get_inner_text, separate_from_list, set_page, get_kwarg
from rtlib.types_ import UserMember
from rtlib.help import make_default
from rtlib import RT, Cog, t

from data import get_category


FIRST_OF_HELP = {
    "ja": "ここには、RTの使い方が載っています。\n下にあるセレクトボックスでカテゴリーとコマンドを選択することができます。",
    "en": "Here you will find how to use RT.\nYou can select the category and command in the select box below the ߋn."
}


EmbedParts = NamedTuple("EmbedParts", (
    ("level", Literal[0, 1, 2]), ("title", str), ("description", str | list[str]),
    ("category_name", str | None), ("command_name", str | None), ("over", bool)
))


class HelpSelect(discord.ui.Select):
    "ヘルプパネルで使うコマンドかカテゴリーを選択するためのセレクトです。"

    view: HelpView

    def __init__(
        self, mode: Literal["category", "command"], options: Sequence[tuple[str, str, str]],
        category: str | None, command: str | None, *args, **kwargs
    ):
        self.category, self.command = category, command
        super().__init__(*args, **kwargs)
        self.mode = mode
        for option in options:
            self.add_option(label=option[0], value=option[2], description=option[1])

    async def callback(self, interaction: discord.Interaction):
        if await check(self.view, interaction):
            category, command = None, None
            if self.mode == "category":
                category = self.values[0]
            else:
                command = self.values[0]
                category = self.category
            view = HelpView(
                self.view.cog, self.view.language, self.view.cog.make_parts(
                    self.view.language, category, command
                ), self.view.target # type: ignore
            )
            await interaction.response.edit_message(embed=view.page.embeds[0], view=view)
            view.set_message(interaction)


class HelpView(TimeoutView):
    "ヘルプのカテゴリーやコマンドの選択用のセレクトのViewです。"

    def __init__(
        self, cog: Help, language: str, parts: EmbedParts,
        target: UserMember, *args, **kwargs
    ):
        self.cog, self.language = cog, language
        self.parts, self.target = parts, target

        super().__init__(*args, **kwargs)

        # 2000文字を超えている場合はDiscordで表示しきれない。そのため、分割を行う。
        embeds: list[discord.Embed] = []
        if isinstance(self.parts[2], str):
            embeds = list(separate_to_embeds(
                self.parts[2], lambda x: Cog.Embed(self.parts[1], description=x), # type: ignore
                lambda text: text[:2000]
            ))
        else:
            # 文字列のリストの場合は、既に分割されてるということなので、そのまま追加する。
            embeds = []
            for text in self.parts[2]:
                embeds.append(Cog.Embed(self.parts[1], description=text))

        length = len(embeds)
        self.page = NoEditEmbedPage(embeds)
        if length != 1:
            # 複数ページにわたるヘルプの場合はEmbedPageのアイテムを付ける。
            set_page(embeds, length=length)
            for item in self.page.children:
                if getattr(item, "custom_id") != "BPViewCounter":
                    self.add_item(item)

        self.add_item(HelpSelect("category", [
            (get_category(category, language), category, category)
            for category in self.cog.data.keys()
        ], self.parts.category_name, self.parts.command_name, placeholder=t(dict(
            ja="カテゴリー", en="Category"
        ), target)))
        if self.parts.category_name is not None:
            self.add_item(HelpSelect("command", [
                (name, detail.headline.get(language, "..."), name)
                for name, detail in self.cog.data[self.parts.category_name].items() # type: ignore
            ], self.parts.category_name, self.parts.command_name, placeholder=t(dict(
                ja="コマンド", en="Command"
            ), target)))


RESULT_TYPES = {
    "contain": {"ja": "コマンド名部分一致", "en": "partial command name match"},
    "detail_contain": {"ja": "説明部分一致", "en": "partial description match"}
}


class Help(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data: defaultdict[str, dict[str, Cog.Help]] = defaultdict(dict)

    @commands.Cog.listener()
    async def on_load(self):
        await self.aioload()

    def make_other_command_help(self, command: commands.Command | commands.Group) -> Cog.Help:
        "`HelpCommand`が用意されていないコマンドから自動でヘルプオブジェクトを作る。"
        assert command.callback.__doc__ is not None or command.description
        return Cog.HelpCommand(command, False) \
            .set_description(**make_default(command.callback.__doc__ or command.description))

    async def aioload(self):
        "ヘルプを非同期に読み込みます。"
        await self.bot.loop.run_in_executor(None, self.load)

    def load(self):
        "ヘルプを読み込む。"
        self.data = defaultdict(dict)
        for command in self.bot.commands:
            value: Optional[Cog.Help] = getattr(command.callback, "__help__", None)
            if value is not None and not getattr(command.callback, "__raw_help__", False):
                self.data[value.category][command.name] = value
                if self.data[value.category][command.name].category == "Other":
                    if command.cog is not None:
                        path = getfile(command.cog.__class__)
                        path = path[:path.rfind("/")]
                        path = path[path.rfind("/")+1:]
                        self.data[path][command.name] = self.data[value.category][command.name]
                        del self.data[value.category][command.name]
                        self.data[path][command.name].set_category(path)
            elif (command.callback.__doc__ or command.description) \
                    and get_kwarg(command, "category", None) is None:
                # ヘルプオブジェクトが実装されていないものは自動生成を行う。
                self.data["Other"][command.name] = self.make_other_command_help(command)
                if isinstance(command, commands.Group):
                    for target in command.walk_commands():
                        self.data["Other"][command.name].add_sub(
                            self.make_other_command_help(target)
                        )
        self.bot.dispatch("help_load")

    def make_parts(
        self, language: str, category_name: Optional[str] = None,
        command_name: Optional[str] = None
    ) -> EmbedParts:
        "ヘルプ用の埋め込みのパーツを作る。"
        level = 0
        description, title = FIRST_OF_HELP[language], "Help"
        command, category = None, None
        if command_name is not None and category_name is not None:
            level = 2
            title = command_name
            description = list(separate_from_list(
                self.data[category_name][command_name].get_str_list(language)
            ))
            category, command = category_name, command_name
        elif category_name is not None:
            level = 1
            description = "\n".join(
                f"`{name}` {help_.headline.get(language, '...')}"
                for name, help_ in list(self.data[category_name].items())
            )
            title = category_name
            category = category_name
        return EmbedParts(
            level, title, description, category, command,
            level != 0 and len(description) > 2000
        )

    def make_view(self, language: str, category: str, command: str, ctx: Any) -> HelpView:
        "渡された情報から、コマンドのヘルプのデータが格納されたViewのインスタンスを作ります。"
        return HelpView(self, language, self.make_parts(
            language, category, command
        ), ctx)

    @commands.command(
        aliases=("h", "ヘルプ", "助けて", "へ", "HelpMe,RITSUUUUUU!!"),
        description="Displays how to use RT."
    )
    @discord.app_commands.describe(word="Search word or command name")
    async def help(self, ctx: commands.Context, *, word: Optional[str] = None) -> None:
        language = self.bot.get_language("user", ctx.author.id)
        found, category, command = False, None, None

        if word is None:
            found = True
        else:
            # ヘルプを検索する。全一致時は即終了する。
            result: defaultdict[Literal["contain", "detail_contain"], list[tuple[str, str]]] = \
                defaultdict(list)
            for category in list(self.data.keys()):
                if category == word:
                    command = None; found = True; break
                for command, detail in list(self.data[category].items()):
                    if command == word:
                        found = True; break
                    if word in command:
                        result["contain"].append((category, command))
                    if word in detail.description.get(language, "...") \
                            or any(word in extra for extra in list(detail.extras.values())):
                        result["detail_contain"].append((category, command))
                else: continue
                break

        if found:
            # 全一致した場合
            view = HelpView(self, language, self.make_parts(
                language, category, command
            ), ctx.author)
            view.set_message(ctx, await ctx.reply(embed=view.page.embeds[0], view=view))
        else:
            # 検索結果の場合
            view = EmbedPage(list(separate_to_embeds(
                "\n\n".join("\n".join((
                    f"**{get_inner_text(RESULT_TYPES, key, language)}**", "\n".join(
                        f"`{name}` {headline}"
                        for name, headline in map(
                            lambda x: (x[1], self.data[x[0]][x[1]].headline.get(language, "...")),
                            result[key] # type: ignore
                        )
                    ) or "..."
                )) for key in ("contain", "detail_contain")),
                lambda text: self.embed(description=text)
            )))
            if view.length > 1:
                view.set_message(ctx, await ctx.reply(embed=view.embeds[0], view=view))
            else:
                await ctx.reply(embed=view.embeds[0])

    Cog.HelpCommand(help) \
        .add_arg(
            "word", "str", "Optional",
            ja="検索ワードまたはコマンド名", en="Search word or command name"
        ) \
        .set_description(ja="RTの使い方を表示するヘルプコマンドです。", en="Help command to see how to use RT.") \
        .update_headline(ja="RTの使用方法を表示します。")


async def setup(bot):
    await bot.add_cog(Help(bot))