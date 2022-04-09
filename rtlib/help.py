# RT - Help Dataclass

from __future__ import annotations

from inspect import cleandoc

from discord.ext.fslash import _get

from ._types import CmdGrp, Text


__all__ = ("Help", "CONV", "ANNOTATIONS", "cleantext")


def cleantext(text: Text) -> Text:
    "渡された辞書の文字列の値を掃除します。"
    return {key: cleandoc(value) for key, value in text.items()}


CONV = {"ja": "のメンションか名前またはID", "en": " mention, name or id"}
ANNOTATIONS = {
    "Member": {"ja": f"メンバー{CONV['ja']}", "en": f"Member{CONV['en']}"},
    "User": {"ja": f"ユーザー{CONV['ja']}", "en": f"User{CONV['en']}"},
    "Channel": {"ja": f"チャンネル{CONV['ja']}", "en": f"Channel{CONV['en']}"},
    "Guild": {"ja": f"サーバー{CONV['ja']}", "en": f"Server{CONV['en']}"},
    "Thread": {"ja": f"スレッド{CONV['ja']}", "en": f"Thread{CONV['en']}"},
    "Role": {"ja": f"ロール{CONV['ja']}", "en": f"Role{CONV['en']}"},
    "int": {"ja": "整数", "en": "Integer"}, "float": {"ja": "数字", "en": "Number"},
    "str": {"ja": "文字列", "en": "Text"}
}


class Help:
    def __init__(self, command: CmdGrp):
        self.command = command
        self.fsparent = _get(command, "fsparent", None)
        self.description = ""
        self.args: list[tuple[str, str | Text, Text]] = []
        self.extras: dict[str, Text] = {}
        self.headline = {"ja": "...", "en": "..."}
        self.sub: list[Help] = []

        setattr(self.command, "__help__", self)

    def set_description(self, **text: str) -> Help:
        self.description = cleantext(text)
        return self

    def add_arg(self, name: str, annotation: str | Text, **detail: str) -> Help:
        self.args.append((name, annotation, cleantext(detail)))
        return self

    def set_extras(self, name: str, **detail: str) -> Help:
        self.extras[name] = cleantext(detail)
        return self

    def set_headline(self, **headline: str) -> Help:
        self.headline = cleantext(headline)
        return self

    def extend(self, help_: Help) -> Help:
        self.sub.append(help_)
        return self

    @property
    def message_command(self) -> str:
        return self.command.qualified_name

    @property
    def slash_command(self) -> str:
        return self.message_command.replace(
            "rt!", f"/{'' if self.fsparent is None else f'{self.fsparent} '}"
        )

    def to_str(self, language: str) -> str:
        return f"""**{self.command.name}**\n{self.description}\n\n`{self.command.name} {
            self.command.signature
                .replace("[", "[*").replace("]", "*]")
                .replace("<", "<*").replace(">", "*>")
        }`\n\n{"\n".join(
            "".join((
                f"*{name}* : *", (
                    ANNOTATIONS.get(annotation, dict(ja=annotation, en=annotation))
                    if isinstance(annotation, str) else annotation
                )[language], "*\n",
                f"{''.join(f'　　{line}' for line in detail[language].splitlines())})"
            )) for name, annotation, detail in self.args
        )}\n\n{
            "\n\n".join(
                f"**#** {key}\n{text.get(language, '...')}"
                for key, text in self.extras.items()
            )
        }"""

    def get_full_str(self, language: str) -> str:
        return "\n\n".join(self.get_str_list(language))

    def get_str_list(self, language: str) -> list[str]:
        return [h.to_str(language) for h in self.sub]

    def __str__(self) -> str:
        return f"<Help command={self.command}>"