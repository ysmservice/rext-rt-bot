# RT - Help

from __future__ import annotations

from typing import Literal, Optional, NamedTuple
from collections.abc import Sequence

from collections import defaultdict

from discord.ext.fslash import _get
from discord.ext import commands
import discord

from rtlib.views import EmbedPage
from rtlib.help import prepare_default
from rtlib import RT, Cog, t

from data import get_category


FIRST_OF_HELP = {
    "ja": "ここには、RTの使い方が載っています。\n下にあるセレクトボックスでカテゴリーとコマンドを選択することができます。",
    "en": "Here you will find how to use RT.\nYou can select the category and command in the select box below the ߋn."
}


EmbedParts = NamedTuple("EmbedParts", (
    ("level", Literal[0, 1, 2]), ("title", str), ("description", str),
    ("category_name", str | None), ("command_name", str | None), ("over", bool)
))


class HelpSelect(discord.ui.Select):
    "Command or category select"

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
        category, command = None, None
        if self.mode == "category":
            print(self.values[0])
            category = self.values[0]
        else:
            command = self.values[0]
            category = self.category
        view = HelpView(
            self.view.cog, self.view.language, self.view.cog.make_parts(
                self.view.language, category, command
            )
        )
        await interaction.response.edit_message(embed=view.page.embeds[0], view=view)


class HelpView(discord.ui.View):
    "Help panel view"

    def __init__(
        self, cog: Help, language: str, parts: EmbedParts,
        *args, **kwargs
    ):
        self.cog, self.language = cog, language
        self.parts = parts

        super().__init__(*args, **kwargs)

        embeds: list[discord.Embed] = []
        embeds = EmbedPage.prepare_embeds(
            self.parts[2], lambda x: Cog.Embed(self.parts[1], description=x)
        )
        length = len(embeds)
        self.page = EmbedPage(embeds)
        if length != 1:
            for i, embed in enumerate(embeds, 1):
                embed.set_footer(text=f"{i}/{length}")
            for item in self.page.children:
                self.add_item(item)

        self.add_item(HelpSelect("category", [
            (get_category(category, language), category, category)
            for category in self.cog.data.keys()
        ], self.parts.category_name, self.parts.command_name))
        print(self.parts)
        if self.parts.category_name is not None:
            self.add_item(HelpSelect("command", [
                (name, detail.headline.get(language, "..."), name)
                for name, detail in self.cog.data[self.parts.category_name].items() # type: ignore
            ], self.parts.category_name, self.parts.command_name))


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
        self.load()

    def load(self):
        "Load help"
        for command in self.bot.walk_commands():
            value: Optional[Cog.Help] = getattr(command.callback, "__help__", None)
            if value is not None:
                self.data[value.category][command.name] = value
            elif command.callback.__doc__ and _get(command, "category", None) is None:
                self.data["Other"][command.name] = Cog.HelpCommand(command) \
                    .set_description(**prepare_default(command.callback.__doc__))
        self.bot.dispatch("help_load")

    def make_parts(
        self, language: str, category_name: Optional[str] = None,
        command_name: Optional[str] = None
    ) -> EmbedParts:
        "Make embed parts"
        level = 0
        description, title = FIRST_OF_HELP[language], "Help"
        command, category = None, None
        if command_name is not None and category_name is not None:
            level = 2
            description = self.data[category_name][command_name].get_full_str(language)
            title = command_name
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

    @commands.command(
        aliases=("h", "ヘルプ", "助けて", "へ", "HelpMe,RITSUUUUUU!!"),
        description="Displays how to use RT.", category="rt"
    )
    @discord.app_commands.describe(word="Search word or command name")
    async def help(self, ctx: commands.Context, *, word: Optional[str] = None) -> None:
        language = self.bot.get_language("user", ctx.author.id)
        found, category, command = False, None, None

        if word is None:
            found = True
        else:
            result: defaultdict[Literal["contain", "detail_contain"], list[tuple[str, str]]] = \
                defaultdict(list)
            for category in list(self.data.keys()):
                if category == word:
                    found = True; break
                for command, detail in list(self.data[category].items()):
                    if command == word:
                        found = True; break
                    if word in command:
                        result["contain"].append((category, command))
                    if word in detail.description.get(language, "...") \
                            or any(word in extra for extra in list(detail.extras.values())):
                        result["detail_contain"].append((category, command))
            else:
                await ctx.reply(t(dict(ja="見つかりませんでした。", en="Not found...")))
                return

        if found:
            view = HelpView(self, language, self.make_parts(language, category, command))
            await ctx.reply(embed=view.page.embeds[0], view=view)
        else:
            view = EmbedPage(EmbedPage.prepare_embeds(
                "".join((Cog.utils.get(RESULT_TYPES, key, language), "\n".join(
                    f"`{name}` {headline}"
                    for name, headline in map(
                        lambda x: (x[1], self.data[x[0]][x[1]].headline.get(language, "...")),
                        result[key] # type: ignore
                    )
                )) for key in ("contain", "detail_contain")),
                lambda text: self.embed(description=text)
            ))
            await ctx.reply(embed=view.embeds[0], view=view)

    Cog.HelpCommand(help) \
        .add_arg(
            "word", "str", "Optional",
            ja="検索ワードまたはコマンド名", en="Search word or command name"
        ) \
        .set_description(ja="RTの使い方を表示するヘルプコマンドです。", en="Help command to see how to use RT.") \
        .update_headline(ja="RTの使用方法を表示します。")


async def setup(bot):
    await bot.add_cog(Help(bot))