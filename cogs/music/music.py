# RT Music - Data Class

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias, Literal, Union, Any

from warnings import warn

from os.path import exists
from time import time

import discord

from niconico.niconico import NicoNico
from niconico.objects import Video, MyListItemVideo
from yt_dlp import YoutubeDL
from requests import get

from data import TEST

from .types_ import MusicType

if TYPE_CHECKING:
    from .__init__ import MusicCog


# youtube_dlの音楽再生時に使用するオプション
NORMAL_OPTIONS = {
    "format": "bestaudio/best",
    "default_search": "auto",
    "logtostderr": False,
    "cachedir": False,
    "ignoreerrors": True,
    "source_address": "0.0.0.0"
}
# youtube_dlで音楽情報の取得のみの時にに使うオプション
FLAT_OPTIONS = {
    "extract_flat": True,
    "source_address": "0.0.0.0",
    "cookiefile": "data/youtube-cookies.txt"
}
# クッキーの情報が書き込まれているファイルがある場合はそれを設定する。
if exists("data/cookies.txt"):
    NORMAL_OPTIONS["cookiefile"] = "data/youtube-cookies.txt"
    FLAT_OPTIONS["cookiefile"] = "data/youtube-cookies.txt"
elif not TEST:
    warn("No cookies are set. So I will not be able to access some videos on YouTube.")


# FFmpeg用の再接続するようにするためのオプション
FFMPEG_BEFORE_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTIONS = "-vn"


def make_youtube_url(data: dict[str, Any]) -> str:
    "渡されたYouTubeの動画データからYouTubeの動画URLを作ります。"
    return "https://www.youtube.com/watch?v=%s" \
        % data.get("display_id", data.get("id", "3JW1qw7HB5U"))


def time_to_text(time_: int | float) -> str:
    "経過した時間を`01:39`のような`分：秒数`の形にフォーマットする。"
    return ":".join(
        map(lambda o: (
            str(int(o[1])).zfill(2)
            if o[0] or o[1] <= 60
            else time_to_text(o[1])
        ), ((0, time_ // 60), (1, time_ % 60)))
    )


niconico = NicoNico()
def get_niconico_music(
    cog: MusicCog, author: discord.Member, url: str,
    video: Video | MyListItemVideo
) -> Music:
    "ニコニコ動画のMusicクラスのインスタンスを用意する関数です。"
    return Music(
        cog, author, MusicType.niconico, video.title, url,
        video.thumbnail.url, video.duration
    )


def get_youtube_data(url: str, mode: Literal["normal", "flat"]) -> dict[str, Any]:
    "YouTubeのデータを取得する関数です。"
    return YoutubeDL(globals()[f"{mode.upper()}_OPTIONS"]).extract_info(url, download=False)


def is_url(url: str) -> bool:
    "渡された文字列がURLかどうかを返します。"
    return url.startswith(("http://", "https://"))


_GetSourceReturnType: TypeAlias = Union["Music", tuple[list["Music"], bool]]
GetSourceReturnType: TypeAlias = _GetSourceReturnType | Exception
class Music:
    "音楽の情報を格納するデータクラスです。"

    def __init__(
        self, cog: MusicCog, author: discord.Member, type_: int,
        title: str, url: str, thumbnail: str, duration: int | None
    ):
        self.cog, self.author, self.type_, self.title = cog, author, type_, title
        self.url, self.thumbnail, self.duration = url, thumbnail, duration
        self.tag = f"<Music url={self.url} guild_id={author.guild.id}>"

        self.started_at, self.error_time = None, 0
        self.on_close = None

    def close(self) -> None:
        "音楽再生終了時に呼ぶべきメソッドです。"
        if self.on_close is not None:
            self.on_close()

    async def make_source(self) -> discord.PCMVolumeTransformer:
        "音源を取得します。"
        return discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(
            await self.cog.bot.loop.run_in_executor(
                self.cog.bot.mixers.executor,
                self._get_direct_source_link
            ), before_options=FFMPEG_BEFORE_OPTIONS, options=FFMPEG_OPTIONS
        ))

    def _get_direct_source_link(self) -> str:
        # 音源のURLを取得する。
        if self.type_ in (MusicType.youtube, MusicType.soundcloud):
            return get_youtube_data(self.url, "normal")["url"]
        elif self.type_ == MusicType.niconico:
            self.video = niconico.video.get_video(self.url)
            self.video.connect()
            self.on_close = self.video.close
            return self.video.download_link
        assert False

    @classmethod
    async def from_url(
        cls, cog: MusicCog, author: discord.Member,
        url: str, max_result: int
    ) -> GetSourceReturnType:
        "URLからこのクラスのインスタンスを作成します。"
        return await cog.bot.loop.run_in_executor(
            cog.bot.mixers.executor, lambda: cls._wrapped_get_music(
                cls, cog, author, url, max_result
            )
        )

    @staticmethod
    def _wrapped_get_music(
        cls: type[Music], cog, author, # type: ignore
        url: str, max_result: int
    ) -> GetSourceReturnType:
        # `_get_music`を実行して、エラーは回収して返します。
        try:
            return cls._get_music(cls, cog, author, url, max_result)
        except Exception as e:
            cog.logger.warn("Failed to get music: %s - %s" % (e, url))
            return e

    @staticmethod
    def _get_music(
        cls: type[Music], cog: MusicCog, # type: ignore
        author: discord.Member, url: str, max_result: int
    ) -> _GetSourceReturnType:
        # 音楽データを取得して、このクラスのインスタンスにします。
        if "nicovideo.jp" in url or "nico.ms" in url:
            # ニコニコ動画
            # マイリストの場合は取得できるだけ取得する。
            if "mylist" in url:
                items, length, count_stop = [], 0, True
                for mylist in niconico.video.get_mylist(url):
                    length += len(mylist.items)
                    items.extend([get_niconico_music(
                        cog, author, item.video.url, item.video
                    ) for item in mylist.items])
                    if length > max_result:
                        items = items[:max_result]
                        break
                else:
                    count_stop = False
                return items, count_stop

            video = niconico.video.get_video(url)
            return get_niconico_music(cog, author, video.url, video.video)
        elif "soundcloud.com" in url or "soundcloud.app.goo.gl" in url:
            # SoundCloud
            # 短縮URLの場合はリダイレクト先が本当の音楽のURLなのでその真のURLを取得する。
            if "goo" in url:
                url = get(url).url

            data = get_youtube_data(url, "flat")
            return cls(
                cog, author, MusicType.soundcloud, data["title"],
                url, data["thumbnail"], data["duration"]
            )
        else:
            # YouTube
            # もし検索の場合は検索するようにURLを変える。
            if not is_url(url):
                url = f"ytsearch15:{url}"

            # 再生リストならできるだけ取得する。
            data = get_youtube_data(url, "flat")
            if data.get("entries"):
                items = []
                for count, entry in enumerate(data["entries"]):
                    if count == max_result:
                        return items, True
                    items.append(cls(
                        cog, author, MusicType.youtube, entry["title"],
                        make_youtube_url(entry),
                        f"http://i3.ytimg.com/vi/{entry['id']}/hqdefault.jpg",
                        entry["duration"]
                    ))
                else:
                    return items, False

            return cls(
                cog, author, MusicType.youtube, data["title"],
                make_youtube_url(data), data["thumbnail"], data["duration"]
            ) 

    def start(self) -> None:
        "経過時間の計測を開始します。"
        self.started_at = time()

    def _check_started_at(self) -> None:
        if self.started_at is None:
            raise ValueError("先に`start`を実行してください。")

    def toggle_pause(self) -> None:
        "経過時間の計測を一時停止します。"
        self._check_started_at()
        assert self.started_at is not None
        if self.error_time:
            self.started_at -= time() - self.error_time
            self.error_time = 0
        else:
            self.error_time = time()

    @property
    def marked_title(self) -> str:
        "マークダウンによるURLリンク済みのタイトルの文字列を返します。"
        return f"[{self.title}]({self.url})"

    @property
    def now(self) -> float:
        "何秒再生してから経過したかです。"
        self._check_started_at()
        assert self.started_at is not None
        return time() - self.started_at

    @property
    def formated_now(self) -> str:
        "フォーマット済みの経過時間です。"
        return time_to_text(self.now)

    @property
    def formated_duration(self) -> str:
        "フォーマット済みの動画の時間です。"
        return "..." if self.duration is None else time_to_text(self.duration)

    @property
    def elapsed(self) -> str:
        "何秒経過したかの文字列です。"
        return f"{self.formated_now}/{self.formated_duration}"

    def make_seek_bar(self, length: int = 15) -> str:
        "どれだけ音楽が再生されたかの絵文字によるシークバーを作る関数です。"
        if self.duration is None:
            return ""
        return "".join((
            (base := "◾" * length)
                [:(now := int(self.now / self.duration * length))],
            "⬜", base[now:])
        )

    def make_embed(self, seek_bar: bool = False, duration_only: bool = False) -> discord.Embed:
        "再生中の音楽を示す埋め込みを作成します。"
        embed = discord.Embed(title="Now playing", color=self.cog.bot.Colors.normal)
        if seek_bar:
            embed.description = self.make_seek_bar()
        embed.add_field(name="Title", value=self.marked_title)
        embed.add_field(name="Time", value=self.formated_duration
            if duration_only else self.elapsed)
        embed.set_thumbnail(url=self.thumbnail)
        embed.set_author(name=self.author.name, icon_url=getattr(self.author.avatar, "url", ""))
        return embed

    def __str__(self) -> str:
        return f"<Music title={self.title} state={self.now}/{self.duration} author={self.author}>"