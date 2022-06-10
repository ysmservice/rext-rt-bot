# RT Util - Utils

from typing import TypeVar, Optional, Any
from collections.abc import Callable, Iterable, Iterator, Sequence

from datetime import datetime, timedelta, timezone

import discord

from core.utils import gettext
from core import t

from data import TEST, CANARY, PERMISSION_TEXTS, Colors


__all__ = (
    "is_json", "unwrap_or", "set_page", "fetch_webhook", "webhook_send",
    "artificially_send", "permissions_to_text", "make_nopermissions_text",
    "JST", "make_datetime_text", "adjust_min_max", "replace_nl"
)


def is_json(data: str) -> bool:
    "渡された文字列がJSONかどうかを調べます。"
    return (data[0] == "{" and data[-1] == "}") or (data[0] == "[" and data[-1] == "]")


# discord.py系
def unwrap_or(obj: object | None, attr: str, default: Any = None):
    "オブジェクトから指定された属性を取り出すことを試みます。"
    return getattr(obj, attr, default)


# 埋め込み系
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


EmbedsT = TypeVar("EmbedsT", bound=Sequence[discord.Embed])
def set_page(
    embeds: EmbedsT, adjustment: Callable[[int, int], str] \
        = lambda i, length: f"{i}/{length}", length: Optional[int] = None
) -> EmbedsT:
    "渡された埋め込み達にページを追記します。"
    length = length or len(embeds)
    for i, embed in enumerate(embeds, 1):
        embed.set_footer(text="".join((
            embed.footer.text or "", "" if embed.footer.text is None else " ",
            adjustment(i, length)
        )))
    return embeds


# Webhook
if CANARY:
    WEBHOOK_NAME = "R2-Tool"
elif TEST:
    WEBHOOK_NAME = "R3-Tool"
else:
    WEBHOOK_NAME = "RT-Tool"


async def fetch_webhook(channel: discord.TextChannel, name: str = WEBHOOK_NAME) \
        -> discord.Webhook | None:
    "ウェブフックを取得します。"
    return discord.utils.get(await channel.webhooks(), name=name)


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
    member: discord.Member, content: str | None = None,
    additional_name: str = "", mode: str = "webhook", **kwargs
) -> discord.WebhookMessage | discord.Message | None:
    "Webhookまたは埋め込みの送信で、あたかも渡されたメンバーが送信したメッセージのように、メッセージを送信します。"
    name = f"{member.display_name}{additional_name}"
    if isinstance(channel, discord.Thread) or mode != "webhook":
        if "wait" in kwargs:
            del kwargs["wait"]
        kwargs.setdefault("embeds", [])
        kwargs["embeds"].insert(0, discord.Embed(
            description=content, color=Colors.normal
        ).set_author(
            name=name, icon_url=getattr(member.display_avatar, "url", "")
        ))
        return await channel.send(content, **kwargs)
    else:
        kwargs["username"] = name
        return await webhook_send(channel, member, content, **kwargs)


def permissions_to_text(
    permissions: Iterable[str], ctx: Any, margin: str = "`, `",
    left: str = "`", right: str = "`"
) -> str:
    "権限の名前イテラブルを読みやすい名前の文字列にします。"
    return "{}{}{}".format(left, margin.join(
        gettext(value, ctx) if isinstance(ctx, str) else t(value, ctx)
        for key, value in PERMISSION_TEXTS.items()
        if key in permissions
    ), right)


def make_nopermissions_text(permissions: Iterable[str], ctx: Any, **kwargs) -> str:
    "権限がないことを伝えるメッセージの文章を作ります。"
    return (gettext if isinstance(ctx, str) else t)(dict(
        ja="権限がありません。\n必要な権限：%s",
        en="Not authorized.\nRequired Authority: %s"
    ), ctx) % permissions_to_text(permissions, ctx, **kwargs)


JST = timezone(timedelta(hours=9))
def make_datetime_text(time: datetime, format_: str = "%H:%M", timezone: ... = JST) -> str:
    "`datetime.datetime`を文字列にします。また、デフォルトでJSTのタイムゾーンに変換します。"
    time.astimezone(timezone)
    return time.strftime(format_)


def adjust_min_max(
    length: int, min_: int, max_: int, default_min: int = 0,
    default_max: int = 25, reset_value: int = -1
) -> tuple[int, int]:
    "最大値と最低値が`length`より大きい場合はそれに合わせます。"
    if min_ == reset_value:
        min_ = default_min
    if max_ == reset_value:
        max_ = default_max

    if min_ > length:
        min_ = length
    if max_ > length:
        max_ = length

    if min_ < default_min:
        min_ = default_min
    if max_ < default_min:
        max_ = default_min

    if min_ > default_max:
        min_ = default_max
    if max_ > default_max:
        max_ = default_max
    return (min_, max_)


def replace_nl(text: str) -> str:
    "`<nl>`等で区切られているものを改行に交換します。"
    return text.replace("<nl>", "\n").replace("<改行>", "\n") \
            .replace("＜改行＞", "\n")