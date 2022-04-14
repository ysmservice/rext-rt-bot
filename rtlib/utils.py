# RT - Utils

from collections.abc import Callable, Iterator, Sequence

import discord

from ._types import Text


__all__ = ("get_inner_text", "separate", "set_page", "code_block")


def get_inner_text(data: dict[str, Text], key: str, language: str) -> str:
    "渡されたTextが入っている辞書から、特定のキーのTextの指定された言語の値を取り出します。"
    return data[key].get(language, data[key].get("en", key))


def separate(text: str, length: int = 2000) -> Iterator[str]:
    "渡された文字列を指定された数で分割します。"
    while text:
        yield text[:length]
        text = text[length:]


def set_page(
    embeds: Sequence[discord.Embed], adjustment: Callable[[int, int], str] \
        = lambda i, length: f"{i}/{length}"
):
    "渡された埋め込み達にページを追記します。"
    length = len(embeds)
    for i, embed in enumerate(embeds, 1):
        embed.set_footer(text="".join((
            embed.footer.text or "", "" if embed.footer.text is None else " ",
            adjustment(i, length)
        )))


def code_block(code: str) -> str:
    "渡された文字列をコードブロックで囲みます。"
    return f"```\n{code}\n```"