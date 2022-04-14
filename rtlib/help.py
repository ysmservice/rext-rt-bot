# RT - Help Dataclass

from __future__ import annotations

from typing import TypeVar, TypeAlias, Literal
from inspect import cleandoc

from discord.ext.fslash import _get

from ._types import CmdGrp, Text
from .utils import get_inner_text


__all__ = (
    "Help", "CONV", "ANNOTATIONS", "OPTIONS", "EXTRAS", "COMMAND_TYPES",
    "cleantext", "gettext", "make_default"
)


def cleantext(text: Text) -> Text:
    "渡されたTextにある全ての値を`cleandoc`で掃除します。"
    return {key: cleandoc(value) for key, value in text.items()}


def make_default(text: str | Text) -> Text:
    "渡された文字列を日本語と英語のキーがあるTextに入れます。\nTextが渡された場合はそのまま返します。"
    return {"ja": text, "en": text} if isinstance(text, str) else text


CONV = {"ja": "のメンションか名前またはID", "en": " mention, name or id"}
ANNOTATIONS = {
    "Member": {"ja": f"メンバー{CONV['ja']}", "en": f"Member{CONV['en']}"},
    "User": {"ja": f"ユーザー{CONV['ja']}", "en": f"User{CONV['en']}"},
    "Channel": {"ja": f"チャンネル{CONV['ja']}", "en": f"Channel{CONV['en']}"},
    "Guild": {"ja": f"サーバー{CONV['ja']}", "en": f"Server{CONV['en']}"},
    "Thread": {"ja": f"スレッド{CONV['ja']}", "en": f"Thread{CONV['en']}"},
    "Role": {"ja": f"ロール{CONV['ja']}", "en": f"Role{CONV['en']}"},
    "int": {"ja": "整数", "en": "Integer"}, "float": {"ja": "数字", "en": "Number"},
    "str": {"ja": "文字列", "en": "Text"}, "Choice": {"ja": "選ぶ", "en": "Choice"}
}
OPTIONS = {
    "Optional": {"ja": "オプション", "en": "Option"}
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


def gettext(text: Text, language: str) -> str:
    "渡されたTextから指定された言語のものを取り出します。\nもし見つからなかった場合は英語、日本語、それ以外のどれかの順で代わりのものを返します。"
    last = "Translations not found..."
    for key, value in text.items():
        if key == language:
            return value
        last = value
    else:
        return text.get("en") or text.get("ja") or last


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

    def extras_text(self, language: str) -> str:
        return "\n\n".join(
            f"**#** {gettext(EXTRAS.get(key, make_default(key)), language)}\n{gettext(text, language)}"
            for key, text in self.extras.items()
        )

    def to_str(self, language: str) -> str:
        return "".join((
            f"**{self.title}**\n{gettext(self.description, language)}",
            f"\n\n{self.extras_text(language)}"
        ))

    def get_full_str(self, language: str) -> str:
        return '{}{}'.format(self.to_str(language), "".join(self.get_str_list(language)))

    def get_str_list(self, language: str) -> list[str]:
        return [h.to_str(language) for h in self.sub]

    def add_sub(self: SelfT, sub: Help) -> SelfT:
        self.sub.append(sub)
        return self

    def __str__(self) -> str:
        return f"<Help title={self.title}>"


def concat(data: Text, plus: Text, space: str = "") -> Text:
    "TextとTextを連結させます。"
    data = {}
    for key, value in list(data.items()):
        data[key] = f'{value}{space}{plus.get(key, plus.get("en", key))}'
    return data


CmdType: TypeAlias = Literal["message", "slash"] | str
SelfCmdT = TypeVar("SelfCmdT", bound="HelpCommand")
class HelpCommand(Help):
    "ヘルプオブジェクトを継承したコマンドから簡単にヘルプを構成できるようにしたヘルプオブジェクトです。"

    def __init__(self, command: CmdGrp):
        self.command = command
        self.fsparent = _get(command, "fsparent", None)
        self.args: list[tuple[str, Text, Text | None, Text]] = []
        super().__init__()
        setattr(self.command._callback, "__help__", self)
        self.set_headline(en=command.description)
        self.set_title(self.command.name)
        self.set_category(_get(self.command, "category", "Other"))

    def add_arg(
        self: SelfCmdT, name: str, annotation: str | Text,
        option: str | Text | None = None, **detail: str
    ) -> SelfCmdT:
        if isinstance(annotation, str):
            annotation = ANNOTATIONS.get(annotation, annotation)
        if isinstance(option, str):
            option = OPTIONS.get(option, option)
        self.args.append((
            name, make_default(annotation),
            None if option is None else make_default(option),
            cleantext(detail)
        ))
        return self

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
        return "\n".join((
            "".join((
                f"{self.get_type_text(t, language)}: `{getattr(self, f'{t}_qualified')}",
                f" {get_inner_text(args, t, language)}" if args else (
                    f" {self.command.signature}" if self.command.signature else ""
                ), "`"
            )) for t in ("message", "slash")
        ))

    def set_examples(self: SelfCmdT, args: Text, detail: Text) -> SelfCmdT:
        data = concat({
            key: self.full_qualified(
                key, {"message": args, "slash": args}
            ) for key in ("ja", "en")
        }, detail)
        if "Examples" in self.extras:
            self.extras["Examples"] = concat(self.extras["Examples"], data, "\n")
        else:
            self.set_extra("Examples", **data)
        return self

    def args_text(self, language: str) -> str:
        return "".join(("\n".join("".join((
            f"{name} : ", gettext(annotation, language),
            "" if option is None else f", {gettext(option, language)}",
            "\n{}".format(
                '\n'.join(f'　　{line}' for line in gettext(detail, language).splitlines())
            )
        )) for name, annotation, option, detail in self.args), "\n\n")) if self.args else "\n"

    def to_str(self, language: str) -> str:
        return "".join((
            f"**{self.title}**\n\n" if self.command.parent else "",
            f"{gettext(self.description, language)}\n\n**#** ",
            f"{get_inner_text(EXTRAS, 'How', language)}\n",
            f"{self.full_qualified(language)}\n",
            self.args_text(language), self.extras_text(language)
        ))