# RT Music - Types

from typing import TypedDict


class MusicType:
    "音楽の種類です。"

    youtube = 0
    niconico = 1
    soundcloud = 2


class MusicRaw(TypedDict):
    "プレイリストに保存する際の音楽データの辞書の型です。"

    type: int
    title: str
    url: str
    thumbnail: str
    duration: int | None