# RT - Help Dataclass

from __future__ import annotations

from typing import TypeVar, TypeAlias, Literal
from inspect import cleandoc

from discord.ext.fslash import _get

from ._types import CmdGrp, Text
from .utils import get


__all__ = (
    "Help", "CONV", "ANNOTATIONS", "OPTIONS",
    "EXTRAS", "COMMAND_TYPES", "cleantext"
)


def cleantext(text: Text) -> Text:
    "渡された辞書の文字列の値を掃除します。"
    return {key: cleandoc(value) for key, value in text.items()}


def prepare_default(text: str | Text) -> Text:
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
    "How To": {"ja": "使い方"}
}
COMMAND_TYPES = {
    "message": {"ja": "メッセージ"}, "slash": {"ja": "スラッシュ"},
    "ctxUser": {"ja": "ユーザーコンテキストメニュー", "en": "User context menu"},
    "ctxMessage": {"ja": "メッセージコンテキストメニュー", "en": "Message context menu"},
}


SelfT = TypeVar("SelfT", bound="Help")
class Help:
    def __init__(self, title: str, category: str):
        self.title = title
        self.description = {"ja": "...", "en": "..."}
        self.extras: dict[str, Text] = {}
        self.headline = {"ja": "...", "en": "..."}
        self.category = category
        self.sub: list[Help] = []

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

    def extend(self: SelfT, help_: Help) -> SelfT:
        self.sub.append(help_)
        return self

    def extras_text(self, language: str) -> str:
        return "\n\n".join(
            f"**#** {EXTRAS.get(key, key)}\n{text.get(language, '...')}"
            for key, text in self.extras.items()
        )

    def to_str(self, language: str) -> str:
        return f"{self.description}\n\n{self.extras_text(language)}"

    def get_full_str(self, language: str) -> str:
        return '{}\n\n{}'.format(self.to_str(language), "\n\n".join(self.get_str_list(language)))

    def get_str_list(self, language: str) -> list[str]:
        return [h.to_str(language) for h in self.sub]

    def __str__(self) -> str:
        return f"<Help title={self.title}>"


def concat(data: Text, plus: Text, space: str = "") -> Text:
    data = {}
    for key, value in list(data.items()):
        data[key] = f'{value}{space}{plus.get(key, plus.get("en", key))}'
    return data


CmdType: TypeAlias = Literal["message", "slash"] | str
SelfCmdT = TypeVar("SelfCmdT", bound="HelpCommand")
class HelpCommand(Help):
    def __init__(self, command: CmdGrp):
        self.command = command
        self.fsparent = _get(command, "fsparent", None)
        self.args: list[tuple[str, Text, Text | None, Text]] = []
        super().__init__(self.command.name, _get(self.command, "category", "Other"))
        setattr(self.command._callback, "__help__", self)
        self.set_headline(en=command.description)

    def add_arg(
        self: SelfCmdT, name: str, annotation: str | Text,
        option: str | Text | None = None, **detail: str
    ) -> SelfCmdT:
        if isinstance(annotation, str):
            annotation = ANNOTATIONS.get(annotation, annotation)
        if isinstance(option, str):
            option = OPTIONS.get(option, option)
        self.args.append((
            name, prepare_default(annotation),
            None if option is None else prepare_default(option),
            cleantext(detail)
        ))
        return self

    @property
    def message_qualified(self) -> str:
        return self.command.qualified_name

    @property
    def slash_qualified(self) -> str:
        return self.message_qualified.replace(
            "rt!", f"/{'' if self.fsparent is None else f'{self.fsparent} '}"
        )

    def get_type_text(self, type_: CmdType, language: str):
        return get(COMMAND_TYPES, type_, language)

    @property
    def marked_property(self) -> str:
        return self.command.signature \
            .replace("[", "[*").replace("]", "*]") \
            .replace("<", "<*").replace(">", "*>")

    def full_qualified(self, language: str, args: dict[CmdType, Text] = {}) -> str:
        return "\n".join((
            "".join((
                f"{self.get_type_text(t, language)}: `{getattr(self, f'{t}_qualified')}",
                f" {get(args, t, language)}`" if args else '`'
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
        return "\n".join("".join((
            f"*{name}* : *", annotation.get(language, "..."), "*",
            "" if option is None else f", {option}",
            f"{''.join(f'　　{line}' for line in detail.get(language, '...').splitlines())})"
        )) for name, annotation, option, detail in self.args)

    def to_str(self, language: str) -> str:
        return "".join((
            f"{self.description}\n\n**#** {get(EXTRAS, 'How', language)}\n",
            f"{self.full_qualified(language)}\n{self.args_text(language)}\n\n",
            self.extras_text(language)
        ))