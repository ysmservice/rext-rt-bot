# RT - Utils

from typing import Optional, Any
from collections.abc import Callable, Iterator, Sequence

from inspect import cleandoc

import discord

from .types_ import Text


__all__ = (
    "get_inner_text", "separate", "separate_from_list", "set_page", "code_block",
    "to_dict_for_dataclass", "get_name_and_id_str", "gettext", "cleantext",
    "make_default"
)


# 言語関連
def get_inner_text(data: dict[str, Text], key: str, language: str) -> str:
    "渡されたTextが入っている辞書から、特定のキーのTextの指定された言語の値を取り出します。"
    return data[key].get(language, data[key].get("en", key))


def gettext(text: Text, language: str) -> str:
    "渡されたTextから指定された言語のものを取り出します。\nもし見つからなかった場合は英語、日本語、それ以外のどれかの順で代わりのものを返します。"
    last = "Translations not found..."
    for key, value in text.items():
        if key == language:
            return value
        last = value
    else:
        return text.get("en") or text.get("ja") or last


def cleantext(text: Text) -> Text:
    "渡されたTextにある全ての値を`cleandoc`で掃除します。"
    return {key: cleandoc(value) for key, value in text.items()}


def make_default(text: str | Text) -> Text:
    "渡された文字列を日本語と英語のキーがあるTextに入れます。\nTextが渡された場合はそのまま返します。"
    return {"ja": text, "en": text} if isinstance(text, str) else text


# その他
def separate(
    text: str,
    extractor: Callable[[str], str]
        = lambda text: text[:2000]
) -> Iterator[str]:
    "渡された文字列を指定された数で分割します。"
    while text:
        extracted = extractor(text)
        text = text.replace(extracted, "", 1)
        yield extracted


def separate_from_list(texts: list[str], max_: int = 2000) -> Iterator[str]:
    "渡された文字列のリストを特定の文字数のタイミングで分割します。"
    length, tentative = 0, ""
    for text in texts:
        length += len(text)
        if length >= max_:
            yield tentative
            length, tentative = 0, ""
        tentative += text
    if tentative:
        yield tentative


def set_page(
    embeds: Sequence[discord.Embed], adjustment: Callable[[int, int], str] \
        = lambda i, length: f"{i}/{length}", length: Optional[int] = None
):
    "渡された埋め込み達にページを追記します。"
    length = length or len(embeds)
    for i, embed in enumerate(embeds, 1):
        embed.set_footer(text="".join((
            embed.footer.text or "", "" if embed.footer.text is None else " ",
            adjustment(i, length)
        )))


def code_block(code: str, type_: str = "") -> str:
    "渡された文字列をコードブロックで囲みます。"
    return f"```{type_}\n{code}\n```"


to_dict_for_dataclass: Callable[..., dict[str, Any]] = lambda self: {
    key: getattr(self, key) for key in self.__class__.__annotations__.keys()
}
"データクラスのデータを辞書として出力する`to_dict`を作成します。"


def get_name_and_id_str(obj: discord.abc.Snowflake):
    "渡されたオブジェクトの名前とIDが書き込まれた文字列を作ります。"
    return f"{obj} (`{obj.id}`)"