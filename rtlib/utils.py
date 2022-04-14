# RT - Utils

from ._types import Text


def get_inner_text(data: dict[str, Text], key: str, language: str) -> str:
    "渡されたTextが入っている辞書から、特定のキーのTextの指定された言語の値を取り出します。"
    return data[key].get(language, data[key].get("en", key))