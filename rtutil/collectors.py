# rtutil - Collectors

from urllib.parse import quote


__all__ = ("make_google_url",)


def make_google_url(query: str, ext: str = "") -> str:
    "Googleの検索のURLを作ります。"
    return "https://www.google.com/search?q=%s%s" % (quote(query), ext)