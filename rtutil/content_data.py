# RT Util - Content Data

from typing import TypedDict, Any

from textwrap import shorten

from discord import Embed

from orjson import loads

from .utils import is_json


__all__ = (
    "ContentData", "disable_content_json", "enable_content_json",
    "convert_content_json", "to_text"
)


class ContentData(TypedDict):
    "`send`で送信可能なJSON形式のデータの型です。"

    content: dict[str, Any]
    author: int
    json: bool


_acj_check_embeds = lambda data, type_: \
    "embeds" in data["content"] and data["content"]["embeds"] \
    and isinstance(data["content"]["embeds"][0], type_)
def disable_content_json(data: ContentData) -> ContentData:
    "ContentDataのデータを`send`等で使える状態にします。"
    if data["json"] and _acj_check_embeds(data, dict):
        for index, embed in enumerate(data["content"]["embeds"]):
            data["content"]["embeds"][index] = Embed.from_dict(embed)
    data["json"] = False
    return data
def enable_content_json(data: ContentData) -> ContentData:
    "ContentDataをJSON形式にできるようにしています。"
    if not data["json"] and _acj_check_embeds(data, Embed):
        for index, embed in enumerate(data["content"]["embeds"]):
            data["content"]["embeds"][index] = embed.to_dict()
    data["json"] = True
    return data


def convert_content_json(content: str, author: int, force_author: bool = False) -> ContentData:
    "渡された文字列をContentDataにします。"
    data = loads(content) if is_json(content) else ContentData(
        content={"content": content}, author=force_author, json=True
    )
    if force_author:
        data["author"] = author
    return data


def to_text(data: ContentData) -> str:
    "ContentDataをちょっとした文字列で表した形式にします。"
    return shorten("".join(data['content'].get(key, "") for key in ("content", "embeds")), 35)