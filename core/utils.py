# RT - Utils

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, Optional, Any
from collections.abc import Coroutine, Callable, Iterator, Iterable, Sequence

from inspect import cleandoc, getfile

from discord.ext import commands
import discord

from discord.ext.fslash import _get as get_kwarg, Context

from rtlib.common.utils import make_error_message

from data import TEST, CANARY, Colors

if TYPE_CHECKING:
    from .types_ import Text, Feature, CmdGrp
    from .log import Target
    from .bot import RT


__all__ = (
    "get_inner_text", "separate", "separate_from_iterable", "set_page",
    "get_name_and_id_str", "gettext", "cleantext", "quick_log",
    "make_default", "get_kwarg", "truncate", "unwrap", "concat_text", "quick_invoke_command",
    "get_fsparent", "webhook_send", "artificially_send"
)


def get_fsparent(obj: Any) -> str:
    "オブジェクトからカテゴリーを取得します。"
    fsparent = getfile(obj)
    fsparent = fsparent[:fsparent.rfind("/")]
    fsparent = fsparent[fsparent.rfind("/")+1:]
    return fsparent


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
def separate_from_iterable(texts: Iterable[str], max_: int = 2000, join: str = "") -> Iterator[str]:
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


def get_name_and_id_str(obj: discord.abc.Snowflake):
    "渡されたオブジェクトの名前とIDが書き込まれた文字列を作ります。"
    return f"{obj} (`{obj.id}`)"


if CANARY:
    WEBHOOK_NAME = "R2-Tool"
elif TEST:
    WEBHOOK_NAME = "R3-Tool"
else:
    WEBHOOK_NAME = "RT-Tool"


async def webhook_send(
    channel: discord.TextChannel, member: discord.Member,
    *args, **kwargs
) -> discord.WebhookMessage:
    "指定されたメンバーの名前とアイコンを使ってWebhookでメッセージを送信します。"
    kwargs.setdefault("username", member.display_name)
    kwargs.setdefault("avatar_url", getattr(member.display_avatar, "url", ""))
    if (webhook := discord.utils.get(await channel.webhooks(), name=WEBHOOK_NAME)) is None:
        webhook = await channel.create_webhook(name=WEBHOOK_NAME, reason="For RT Tool")
    return await webhook.send(*args, **kwargs)


async def artificially_send(
    channel: discord.TextChannel | discord.Thread,
    member: discord.Member, content: str | None,
    *args, additional_name: str = "", **kwargs
) -> discord.WebhookMessage | discord.Message:
    "Webhookまたは埋め込みの送信で、あたかも渡されたメンバーが送信したメッセージのように、メッセージを送信します。"
    name = f"{member.display_name}{additional_name}"
    if isinstance(channel, discord.Thread):
        kwargs.setdefault("embeds", [])
        kwargs["embeds"].insert(0, discord.Embed(
            description=content, color=Colors.normal
        ).set_author(
            name=name, icon_url=getattr(member.display_avatar, "url", "")
        ))
        return await channel.send(*args, **kwargs)
    else:
        kwargs["username"] = name
        return await webhook_send(channel, member, content, *args, **kwargs)