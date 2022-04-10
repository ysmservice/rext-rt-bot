# RT - Data

from typing import TypedDict

from ujson import load

from .constants import CATEGORIES


__all__ = ("SECRET", "get_category")


class Secret(TypedDict):
    token: str
    mysql: dict


with open("secret.json", "r") as f:
    SECRET: Secret = load(f)


def get_category(category: str, language: str) -> str:
    "Get the best category alias from the passed category and language code."
    return CATEGORIES.get(category, {}).get(language, category)