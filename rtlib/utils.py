# RT - Utils

from typing import Optional
from collections.abc import Callable, Iterator, Sequence

import discord

from ._types import Text


__all__ = ("get_inner_text", "separate", "separate_from_list", "set_page", "code_block")


def get_inner_text(data: dict[str, Text], key: str, language: str) -> str:
    "渡されたTextが入っている辞書から、特定のキーのTextの指定された言語の値を取り出します。"
    return data[key].get(language, data[key].get("en", key))


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


def code_block(code: str) -> str:
    "渡された文字列をコードブロックで囲みます。"
    return f"```\n{code}\n```"