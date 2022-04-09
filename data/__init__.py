# RT - Data

from typing import TypedDict

from ujson import load


__all__ = ("SECRET",)


class Secret(TypedDict):
    token: str
    mysql: dict


with open("secret.json", "r") as f:
    SECRET: Secret = load(f)