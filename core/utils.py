# RT - Utils

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from collections.abc import Callable, Iterator

from inspect import cleandoc, getfile
import os

from logging import getLogger

from discord.ext import commands
import discord

from discord.ext.fslash import _get as get_kwarg, Context

from rtlib.common import set_handler

if TYPE_CHECKING:
    from .types_ import Text, CmdGrp
    from .bot import RT


__all__ = (
    "get_inner_text", "separate", "gettext", "cleantext", "make_default",
    "get_kwarg", "truncate", "concat_text", "quick_invoke_command",
    "get_fsparent", "logger"
)
logger = getLogger("rt")
set_handler(logger)


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


def make_default(text: str | Text, **kwargs) -> Text:
    "渡された文字列を日本語と英語のキーがあるTextに入れます。\nTextが渡された場合はそのまま返します。"
    return {"ja": text.format(**kwargs), "en": text.format(**kwargs)} \
        if isinstance(text, str) else text


def concat_text(data: Text, plus: Text, space: str = "") -> Text:
    "TextとTextを連結させます。"
    for key, value in list(data.items()):
        data[key] = f'{value}{space}{plus.get(key, plus.get("en", ""))}'
    return data


# 文字列関連
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


def truncate(text: str, max_: int = 255, end: str = "...") -> str:
    "渡された文字列に、 文字列が長い場合のみ、最後に`...`を付けます。"
    return f"{text[:max_-len(end)]}{end}" if len(text) > max_ else text


# discord.py関連
async def quick_invoke_command(
    bot: RT, cmd: CmdGrp,
    ctx: Context | commands.Context[RT] | discord.Message | discord.Interaction,
    end: str = "", **kwargs
) -> bool:
    "指定されたコマンドを渡されたContextで実行をします。\nエラー時には`on_command_error`を呼び出します。"
    # 引数を入れる。
    if isinstance(ctx, discord.Message):
        ctx.content = ""
        for key, value in kwargs.get("kwargs", {}).items():
            if key != end and " " in value or "　" in value:
                value = f'"{value}"'
            ctx.content += f" {value}"
        ctx.content = ctx.content[1:]

    if isinstance(ctx, discord.Message | discord.Interaction):
        ctx = await bot.get_context(ctx)

    ctx.command = cmd # type: ignore
    for key, value in kwargs.items():
        setattr(ctx, key, value)

    try: await ctx.command.invoke(ctx) # type: ignore
    except Exception as e:
        bot.dispatch("command_error", ctx, e)
        return False
    else: return True