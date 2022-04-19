# RT - Help Dataclass

from __future__ import annotations

from typing import TypeVar, TypeAlias, Literal

from discord.ext.fslash import _get

from .utils import get_inner_text, gettext, cleantext, make_default, concat_text
from .types_ import CmdGrp, Text


__all__ = ("Help", "CONV", "ANNOTATIONS", "OPTIONS", "EXTRAS", "COMMAND_TYPES")


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
    "How": {"ja": "使い方"}
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
        self.title = title
        return self

    def set_description(self: SelfT, **text: str) -> SelfT:
        self.description = cleantext(text)
        return self

    def set_category(self: SelfT, category: str) -> SelfT:
        self.category = category
        return self

    def set_extra(self: SelfT, name: str, **detail: str) -> SelfT:
        self.extras[name] = cleantext(detail)
        return self

    def set_headline(self: SelfT, **headline: str) -> SelfT:
        self.headline = cleantext(headline)
        return self

    def update_headline(self: SelfT, **headline: str) -> SelfT:
        self.headline.update(cleantext(headline))
        return self

    def extras_text(self, language: str, first: str = "") -> str:
        return "{}{}".format(first, "\n\n".join(
            f"**#** {gettext(EXTRAS.get(key, make_default(key)), language)}\n{gettext(text, language)}"
            for key, text in self.extras.items()
        )) if self.extras else ""

    def to_str(self, language: str) -> str:
        return "".join((
            f"**{self.title}**\n{gettext(self.description, language)}",
            f"\n\n{self.extras_text(language)}"
        ))

    def get_full_str(self, language: str) -> str:
        return "\n\n".join(self.get_str_list(language))

    def get_str_list(self, language: str) -> list[str]:
        return [f"{self.to_str(language)}\n\n"] + [
            f"{h.to_str(language)}\n\n" for h in self.sub
        ]

    def add_sub(self: SelfT, sub: Help) -> SelfT:
        self.sub.append(sub)
        return self

    def __str__(self) -> str:
        return f"<Help title={self.title}>"


CmdType: TypeAlias = Literal["message", "slash"] | str
SelfCmdT = TypeVar("SelfCmdT", bound="HelpCommand")
class HelpCommand(Help):
    "ヘルプオブジェクトを継承したコマンドから簡単にヘルプを構成できるようにしたヘルプオブジェクトです。"

    def __init__(self, command: CmdGrp, set_help: bool = True):
        self.command = command
        self.fsparent = _get(command, "fsparent", None)
        self.args: list[tuple[str, Text, Text | None, Text]] = []
        super().__init__()
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

    def set_args(self, **kwargs: tuple):
        for key, value in kwargs.items():
            self.add_arg(key, *value[:-1], **value[-1])

    @property
    def message_qualified(self) -> str:
        return f"rt!{self.command.qualified_name}"

    @property
    def slash_qualified(self) -> str:
        return self.message_qualified.replace(
            "rt!", f"/{'' if self.fsparent is None else f'{self.fsparent} '}"
        )

    def get_type_text(self, type_: CmdType, language: str):
        return get_inner_text(COMMAND_TYPES, type_, language)

    def full_qualified(self, language: str, args: dict[CmdType, Text] = {}) -> str:
        return "\n".join(("".join((
            f"{self.get_type_text(t, language)}: `{getattr(self, f'{t}_qualified')}",
            f" {get_inner_text(args, t, language)}" if args else (
                f" {self.command.signature}" if self.command.signature else ""
            ), "`"
        )) for t in ("message", "slash")))

    def set_examples(self: SelfCmdT, args: Text, detail: Text) -> SelfCmdT:
        data = concat_text({
            key: self.full_qualified(
                key, {"message": args, "slash": args}
            ) for key in ("ja", "en")
        }, detail)
        if "Examples" in self.extras:
            self.extras["Examples"] = concat_text(self.extras["Examples"], data, "\n")
        else:
            self.set_extra("Examples", **data)
        return self

    def args_text(self, language: str, first: str = "") -> str:
        return "{}{}".format(first, "\n\n".join("".join((
            f"{name} : ", gettext(annotation, language),
            "" if option is None else f", {gettext(option, language)}",
            "\n{}".format(
                '\n'.join(f'　　{line}' for line in gettext(detail, language).splitlines())
            )
        )) for name, annotation, option, detail in self.args)) if self.args else ""

    def to_str(self, language: str) -> str:
        return "".join((
            f"**{self.title}**\n\n" if self.command.parent else "",
            f"{gettext(self.description, language)}\n\n**#** ",
            f"{get_inner_text(EXTRAS, 'How', language)}\n",
            self.full_qualified(language), self.args_text(language, "\n\n"),
            self.extras_text(language, "\n\n")
        ))