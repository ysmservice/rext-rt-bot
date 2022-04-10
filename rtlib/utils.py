# RT - Utils

from ._types import Text


def get(data: dict[str, Text], key: str, language: str) -> str:
    return data[key].get(language, data[key].get("en", key))