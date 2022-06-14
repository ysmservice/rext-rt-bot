# RT Util - Collectors

from typing import Any

from collections import defaultdict
from urllib.parse import quote

from aiohttp import ClientSession
from orjson import loads


__all__ = ("make_google_url", "AREA_CODES", "CITY_CODES", "tenki")
with open("data/area_codes.json", "r", encoding="utf-8") as f:
    AREA_CODES = loads(f.read())
CITY_CODES: defaultdict[str, dict[str, str]] = defaultdict(dict)
for pref in AREA_CODES["pref"]:
    for city in pref["city"]:
        CITY_CODES[pref["@title"]][city["@title"]] = city["@id"]


def make_google_url(query: str, ext: str = "") -> str:
    "Googleの検索のURLを作ります。"
    return "https://www.google.com/search?q=%s%s" % (quote(query), ext)


async def tenki(session: ClientSession, city: str) -> dict[str, Any]:
    "天気情報を取得します。"
    async with session.get(f"https://weather.tsukumijima.net/api/forecast/city/{city}") as r:
        return await r.json(loads=loads)