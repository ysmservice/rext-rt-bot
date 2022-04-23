# RT - Utils

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, Optional, Any
from collections.abc import Coroutine, Callable, Iterator, Sequence

from traceback import TracebackException
from inspect import cleandoc

from discord.ext import commands
import discord

from discord.ext.fslash import _get as get_kwarg, Context

if TYPE_CHECKING:
    from .types_ import Text, Feature, CmdGrp
    from .log import Target
    from .bot import RT


__all__ = (
    "get_inner_text", "separate", "separate_from_list", "set_page", "code_block",
    "to_dict_for_dataclass", "get_name_and_id_str", "gettext", "cleantext", "quick_log",
    "make_default", "get_kwarg", "truncate", "unwrap", "concat_text", "make_error_message",
    "quick_invoke_command"
)


def make_error_message(error: Exception) -> str:
    "渡されたエラーから全文を作ります。"
    return "".join(TracebackException.from_exception(error).format())


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


def concat_text(data: Text, plus: Text, space: str = "") -> Text:
    "TextとTextを連結させます。"
    for key, value in list(data.items()):
        data[key] = f'{value}{space}{plus.get(key, plus.get("en", key))}'
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


def code_block(code: str, type_: str = "") -> str:
    "渡された文字列をコードブロックで囲みます。"
    return f"```{type_}\n{code}\n```"


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

    ctx.command = cmd
    for key, value in kwargs.items():
        setattr(ctx, key, value)

    try: await ctx.command.invoke(ctx) # type: ignore
    except Exception as e:
        bot.dispatch("command_error", ctx, e)
        return False
    else: return True


def quick_log(
    self: commands.Cog, feature: Feature, detail: Text,
    target: Target, status: str, more_detail: Optional[Text] = None
) -> None:
    "簡単にログ出力を行います。"
    bot: RT = getattr(self, "bot")
    bot.loop.create_task(bot.log(bot.log.LogData.quick_make(
        feature, status, target, getattr(self, "t")(
            detail if more_detail is None else concat_text(detail, more_detail, "\n"),
            target
        )
    )), name="RT Log")


UPReT = TypeVar("UPReT")
async def unwrap(
    self: commands.Cog, feature: Feature, target: Target,
    coro: Coroutine[Any, Any, UPReT], content: Text, before: Any = None,
    do_success_log: bool = False, do_raise: bool = False
) -> UPReT | Exception:
    "渡されたをtryでラップして実行をします。\n失敗した場合はRTログに流します。"
    make_response = lambda data: quick_log(
        self, feature, content, target, data.pop("status", "ERROR"), data
    )
    try:
        data = await coro
    except discord.Forbidden as e:
        make_response(dict(
            ja="権限がないため処理を完了することができませんでした。",
            en="The process could not be completed due to lack of permissions."
        ))
        return e
    except discord.NotFound as e:
        make_response(dict(
            ja=f"{before}が見つかりませんでした。",
            en=f"{before} was not found."
        ))
        return e
    except Exception as e:
        error = make_error_message(e)
        make_response(dict(
            ja=f"内部エラーが発生したため処理を完了することができませんでした。\nエラー全文：\n{error}",
            en=f"Processing could not be completed due to an internal error.\nFUll text of error:\n{error}"
        ))
        if do_raise: raise
        return e
    else:
        if do_success_log is not None:
            d = {}
            d["status"] = "SUCCESS"
            make_response(d)
        return data


# 埋め込み関連
def separate_from_list(texts: list[str], max_: int = 2000, join: str = "") -> Iterator[str]:
    "渡された文字列のリストを特定の文字数のタイミングで分割します。"
    length, tentative = 0, ""
    for text in texts:
        length += len(text)
        if length >= max_:
            yield f"{tentative}{join}"
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


to_dict_for_dataclass: Callable[..., dict[str, Any]] = lambda self: {
    key: getattr(self, key) for key in self.__class__.__annotations__.keys()
}
"データクラスのデータを辞書として出力する`to_dict`を作成します。"


def get_name_and_id_str(obj: discord.abc.Snowflake):
    "渡されたオブジェクトの名前とIDが書き込まれた文字列を作ります。"
    return f"{obj} (`{obj.id}`)"