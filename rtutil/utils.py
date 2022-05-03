# rtutil - Utils

from typing import Optional
from collections.abc import Callable, Iterable, Iterator, Sequence

import discord

from data import TEST, CANARY, Colors


__all__ = ("set_page", "webhook_send", "artificially_send")


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


# Webhook
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