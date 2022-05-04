# RT - Help Dataclass

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, TypeAlias, Literal, Optional
from collections.abc import Iterator

from collections import defaultdict
from itertools import chain

from discord.ext import commands
from discord.app_commands import Command

from discord.ext.fslash import _get, groups

from rtlib.common.utils import code_block

from .utils import (
    get_kwarg, get_fsparent, get_inner_text, gettext, cleantext,
    make_default, concat_text
)
from . import tdpocket
from .types_ import CmdGrp, Text
from .general import Cog
from .bot import RT

if TYPE_CHECKING:
    from .rtevent import EventContext


__all__ = ("Help", "HelpCore", "CONV", "ANNOTATIONS", "OPTIONS", "EXTRAS", "COMMAND_TYPES")


CONV = {"ja": "のメンションか名前またはID", "en": " mention, name or id"}
ANNOTATIONS = {
    "Member": {"ja": f"メンバー{CONV['ja']}", "en": f"Member{CONV['en']}"},
    "User": {"ja": f"ユーザー{CONV['ja']}", "en": f"User{CONV['en']}"},
    "Channel": {"ja": f"チャンネル{CONV['ja']}", "en": f"Channel{CONV['en']}"},
    "Guild": {"ja": f"サーバー{CONV['ja']}", "en": f"Server{CONV['en']}"},
    "Thread": {"ja": f"スレッド{CONV['ja']}", "en": f"Thread{CONV['en']}"},
    "Role": {"ja": f"ロール{CONV['ja']}", "en": f"Role{CONV['en']}"},
    "Emoji": {"ja": f"絵文字{CONV['ja']}", "en": f"Emoji{CONV['en']}"},
    "int": {"ja": "整数", "en": "Integer"}, "float": {"ja": "数字", "en": "Number"},
    "str": {"ja": "文字列", "en": "Text"}, "Choice": {"ja": "選ぶ", "en": "Choice"},
    "bool": {"ja": "真偽地 (on/off, True/False のいずれか)", "en": "Boolean (any of on/off, True/False)"}
}
OPTIONS = {
    "Optional": {"ja": "オプション", "en": "Option"},
    "default": {"ja": "デフォルト", "en": "defualt"}
}
EXTRAS = {
    "Examples": {"ja": "使用例"}, "Notes": {"ja": "メモ"},
    "Warnings": {"ja": "警告"}, "See Also": {"ja": "参照"},
    "How": {"ja": "使い方"}, "Aliases": {"ja": "エイリアス"}
}
COMMAND_TYPES = {
    "message": {"ja": "メッセージ"}, "slash": {"ja": "スラッシュ"},
    "ctxUser": {"ja": "ユーザーコンテキストメニュー", "en": "User context menu"},
    "ctxMessage": {"ja": "メッセージコンテキストメニュー", "en": "Message context menu"},
}


SelfT = TypeVar("SelfT", bound="Help")
class Help:
    "ヘルプオブジェクトです。\nこれを使用してヘルプの項目を構成します。"

    def __init__(self):
        self.title = "..."
        self.description = {"ja": "...", "en": "..."}
        self.extras: dict[str, Text] = {}
        self.headline = {"ja": "...", "en": "..."}
        self.category = "Other"
        self.sub: list[Help] = []

    gettext = staticmethod(gettext)

    def set_title(self: SelfT, title: str) -> SelfT:
        "タイトルを設定します。"
        self.title = title
        return self

    def set_description(self: SelfT, **text: str) -> SelfT:
        "説明を設定します。"
        self.description = cleantext(text)
        return self

    def set_category(self: SelfT, category: str) -> SelfT:
        "カテゴリーを設定します。"
        self.category = category
        return self

    def set_extra(self: SelfT, name: str, **detail: str) -> SelfT:
        "Extraを設定します。 e.g. Notes"
        self.extras[name] = cleantext(detail)
        return self

    def set_headline(self: SelfT, **headline: str) -> SelfT:
        "見出しを設定します。"
        self.headline = cleantext(headline)
        return self

    def merge_headline(self: SelfT, **headline: str) -> SelfT:
        "見出しをマージします。"
        self.headline.update(cleantext(headline))
        return self

    def extras_text(self, language: str, first: str = "") -> str:
        "Extraの文字列を作ります。"
        return "{}{}".format(first, "\n\n".join(
            f"**#** {gettext(EXTRAS.get(key, make_default(key)), language)}\n{gettext(text, language)}"
            for key, text in self.extras.items()
        )) if self.extras else ""

    def to_str(self, language: str, first: bool = False) -> str:
        "ヘルプを文字列にします。"
        return "".join((
            "" if first else f"**{self.title}**\n",
            f"{gettext(self.description, language)}",
            f"\n\n{self.extras_text(language)}"
        ))

    def get_full_str(self, language: str) -> str:
        "サブコマンドを含めてヘルプを文字列にします。"
        return "\n\n".join(self.get_str_list(language))

    def get_str_list(self, language: str) -> Iterator[str]:
        "このヘルプとサブコマンドのヘルプの文字列のリストを作ります。"
        return chain(f"{self.to_str(language, True)}\n\n", (
            f"{h.to_str(language)}\n\n" for h in self.sub
        ))

    def add_sub(self: SelfT, sub: Help) -> SelfT:
        "サブコマンドを設定します。"
        self.sub.append(sub)
        return self

    def __str__(self) -> str:
        return f"<Help title={self.title}>"


CmdType: TypeAlias = Literal["message", "slash"] | str
SelfCmdT = TypeVar("SelfCmdT", bound="HelpCommand")
class HelpCommand(Help):
    "ヘルプオブジェクトを継承したコマンドから簡単にヘルプを構成できるようにしたヘルプオブジェクトです。"

    def __init__(self, command: CmdGrp, set_help: bool = True, **kwargs):
        self.command = command
        self.fsparent = _get(command, "fsparent", None)
        self.args: list[tuple[str, Text, Text | None, Text]] = []
        super().__init__(**kwargs)
        # ここ以降はコマンドからの自動設定です。
        if set_help: setattr(self.command._callback, "__help__", self)
        else: setattr(self.command._callback, "__raw_help__", self)
        self.set_headline(en=command.description)
        self.set_title(self.command.name)
        self.set_category(_get(self.command, "category", "Other"))
        if command.aliases:
            # エキストラにエイリアスを自動で追加する。
            self.set_extra("Aliases", **make_default(f'`{"`, `".join(command.aliases)}`'))

    def add_arg(
        self: SelfCmdT, name: str, annotation: str | Text,
        option: str | tuple[str, str] | Text | None = None,
        **detail: str
    ) -> SelfCmdT:
        "引数の説明を追加します。"
        if isinstance(annotation, str):
            annotation = ANNOTATIONS.get(annotation, annotation)
        if isinstance(option, str):
            option = make_default(OPTIONS.get(option, option))
        elif isinstance(option, tuple):
            option = make_default(f"{OPTIONS.get(option[0], option[0])} {option[1]}")
        self.args.append((
            name, make_default(annotation),
            option,
            cleantext(detail)
        ))
        return self

    @property
    def message_qualified(self) -> str:
        "コマンドの引数を含めた形式の文字列を作ります。"
        return f"rt!{self.command.qualified_name}"

    @property
    def slash_qualified(self) -> str:
        "スラッシュコマンドの引数を含めた形式の文字列を作ります。"
        return self.message_qualified.replace(
            "rt!", f"/{'' if self.fsparent is None else f'{self.fsparent} '}"
        )

    def get_type_text(self, type_: CmdType, language: str):
        "コマンドの種類を文字列にします。"
        return get_inner_text(COMMAND_TYPES, type_, language)

    def full_qualified(self, language: str, args: dict[CmdType, Text] = {}) -> str:
        "コマンドの引数を含めた形式を作ります。"
        return "\n".join(("".join((
            f"{self.get_type_text(t, language)}: `{getattr(self, f'{t}_qualified')}",
            f" {get_inner_text(args, t, language)}" if args else (
                f" {self.command.signature}" if self.command.signature else ""
            ), "`"
        )) for t in ("message", "slash")))

    def set_examples(self: SelfCmdT, args: Text, detail: Text) -> SelfCmdT:
        "簡単に使用例をヘルプのExtraに登録するためのものです。"
        data = concat_text({
            key: self.full_qualified(
                key, {"message": args, "slash": args}
            ) for key in ("ja", "en")
        }, detail, "\n")
        if "Examples" in self.extras:
            self.extras["Examples"] = concat_text(self.extras["Examples"], data, "\n")
        else:
            self.set_extra("Examples", **data)
        return self

    def args_text(self, language: str, first: str = "") -> str:
        "引数の説明の文字列を作ります。"
        return "{}{}".format(first, "\n".join("".join((
            f"{name} : ", gettext(annotation, language),
            "" if option is None else f", {gettext(option, language)}",
            "\n{}".format(
                '\n'.join(f'　　{line}' for line in gettext(detail, language).splitlines())
            )
        )) for name, annotation, option, detail in self.args)) if self.args else ""

    def set_rtevent(
        self: SelfCmdT, ctx: type[EventContext],
        event_name: str, **detail: str
    ) -> SelfCmdT:
        "RTイベントの説明を入れます。"
        detail = concat_text(concat_text(
            make_default(f"EventName: `{event_name}`"), detail, "\n"
        ), make_default(
            "NoAttrs" if ctx.__name__ == "EventContext" else code_block("\n".join(
                f"{key}\t{value}" for key, value in ctx.__annotations__.items()
            )
        )), "\n")
        self.set_extra("RTEvent", **detail)
        return self

    def to_str(self, language: str, first = False) -> str:
        return "".join((
            f"**{self.command.qualified_name}**\n\n"
                if self.command.parent or not first else "",
            gettext(self.description, language),
            *((
                f"\n\n**#** {get_inner_text(EXTRAS, 'How', language)}\n",
                self.full_qualified(language),
                self.args_text(language, "\n\n")
            ) if not isinstance(self.command, commands.Group) else ()),
            self.extras_text(language, "\n\n")
        ))


Cog.Help = Help
Cog.HelpCommand = HelpCommand


class HelpCore(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.bot.help_ = self
        self.data: defaultdict[str, dict[str, Help]] = defaultdict(dict)

    @commands.Cog.listener()
    async def on_load(self):
        await self.aioload()

    def set_help(self, help_: Help) -> None:
        "ヘルプを追加します。"
        self.data[help_.category][help_.title] = help_

    def make_other_command_help(self, command: commands.Command | commands.Group) -> Help:
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
                        category = get_fsparent(command.cog.__class__)
                        self.data[category][command.name] = \
                            self.data[value.category][command.name]
                        del self.data[value.category][command.name]
                        self.data[category][command.name].set_category(category)
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


async def setup(bot):
    await bot.add_cog(HelpCore(bot))