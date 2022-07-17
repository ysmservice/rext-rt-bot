# RT - Music Player

from __future__ import annotations

from typing import TypeVar, Literal, Any, overload
from collections.abc import Callable, Coroutine

from logging import getLogger

from dataclasses import dataclass
from functools import wraps

from discord.ext import commands
import discord

from core import Cog, RT, t
from core.customer_pool import Plan
from core.utils import concat_text
from rtlib.common.types_ import CoroutineFunction

from rtutil.views import TimeoutView, EasyCallbackSelect

from rtlib.common import set_handler

from .utils import hundred_shorten
from .data_manager import DataManager
from .player import MusicPlayer, LoopMode
from .views import ConfirmView
from .music import Music, is_url

from data import EMOJIS, U_NOT_SBJT


FSPARENT = "music"
command = lambda *args, **kwargs: commands.command(*args, fsparent=FSPARENT, **kwargs)
@dataclass
class Plans:
    "プランをまとめるためのデータクラスです。"

    music_count_per_queue: Plan
    music_count_per_playlist: Plan
    playlist_count: Plan


CmdT = TypeVar("CmdT", bound=commands.Command)
def check(confirm: dict[str, str] | None = None) -> Callable[[CmdT], CmdT]:
    "コマンドを実行することができるかを確認します。また、確認ボタンの作成もできます。"
    def decorator(command: CmdT) -> CmdT:
        original = command.callback
        @commands.cooldown(1, 8, commands.BucketType.user)
        @wraps(command.callback)
        async def new(self: MusicCog, ctx: Cog.Context, *args: Any, **kwargs: Any) -> Any:
            # コマンドを実行することができるかを確認します。
            if ctx.guild not in self.now:
                return await ctx.reply(t(dict(
                    ja="このサーバーで音楽プレイヤーは使われていません。",
                    en="No music player is used on this server."
                ), ctx))

            coro = original(self, ctx, *args, **kwargs) # type: ignore
            if confirm is None:
                return await coro
            else:
                # 必要に応じて確認をする。
                await ConfirmView.process(
                    ctx, confirm, await self.data.get_dj_role(
                        ctx.guild.id
                    ), coro
                )
        command._callback = new # type: ignore
        return command
    return decorator


cog: MusicCog
async def play_autocomplete(_, current: str) -> list[discord.app_commands.Choice]:
    return [discord.app_commands.Choice(name="Never Gonna Give You Up", value="Never Gonna Give You Up")]


make_ask_text = lambda ja, en: {
    "ja": f"みなさんは{ja}して良いと思いますか？",
    "en": f"Do you guys think it is ok to {en}?"
}
class MusicCog(Cog, name="Music"):
    def __init__(self, bot: RT):
        self.bot = bot
        self.logger = getLogger("rt.music")
        set_handler(self.logger)
        self.now: dict[discord.Guild, MusicPlayer] = {}

        self.data = DataManager(self)
        self.plans = Plans(
            self.bot.customers.acquire(100, 1000),
            self.bot.customers.acquire(50, 1000),
            self.bot.customers.acquire(2, 30)
        )

        global cog
        cog = self

    async def cog_load(self):
        await self.data.prepare_table()

    async def cog_unload(self):
        for player in self.now.values():
            await self.bot.mixers.release(player.mixer)

    async def _search_result_select_callback(
        self, select: EasyCallbackSelect,
        interaction: discord.Interaction
    ) -> Any:
        # 検索結果の選択後に呼び出される関数です。
        if getattr(select.view, "author_id") != interaction.user.id:
            return await interaction.response.send_message(
                t(U_NOT_SBJT, interaction), ephemeral=True
            )
        await self._play(
            getattr(select.view, "ctx"), getattr(select.view, "data")[select.values[0]],
            interaction.response.edit_message
        )

    async def _play(
        self, ctx: Cog.Context, query: str | Music,
        reply: CoroutineFunction | None = None
    ) -> None:
        # 音楽再生をする。
        assert ctx.author.voice is not None
        channel = ctx.channel.parent if isinstance(ctx.channel, discord.Thread) else ctx.channel
        if not isinstance(channel, discord.Thread | discord.TextChannel | discord.VoiceChannel):
            raise Cog.reply_error.BadRequest({
                "ja": "このチャンネルではこのコマンドを実行することができません。",
                "en": "This command cannot be executed on this channel."
            })
        # この変数は二回目の`_play`実行かどうか。検索の場合は結果選択があり、選択後の`_play`実行が二回目となる。
        not_twice = reply is None

        # 考え中の旨を伝える。
        message = None
        if not_twice:
            if ctx.interaction is None:
                message = await ctx.reply("%s Now loading..." % EMOJIS["loading"])
            else:
                await ctx.typing()
            reply = ctx.reply if message is None else message.edit

        # まだ接続していない場合は接続を行う。
        if not_twice and ctx.guild not in self.now:
            self.now[ctx.guild] = MusicPlayer(
                self, await self.bot.mixers.acquire_by_member(ctx.author),
                ctx.author.voice.channel
                if isinstance(ctx.author.voice.channel, discord.VoiceChannel) else
                channel
            )

        max_result = await self.plans.music_count_per_queue \
            .calculate(ctx.guild.id)
        if isinstance(query, Music):
            data = query
        else:
            # 音楽を読み込む。
            # if query.startswith("pl:"):
            url = is_url(query)
            data = await Music.from_url(
                self, ctx.author, query,
                (self.now[ctx.guild].length - max_result)
                    if url else 15
            )

            # 検索の場合は選択を要求する。
            if not url:
                assert isinstance(data, tuple)
                data = data[0]

                # Viewを作る。
                view = TimeoutView(timeout=120)
                setattr(view, "data", {})
                setattr(view, "author_id", ctx.author.id)
                setattr(view, "ctx", ctx)
                select = EasyCallbackSelect(self._search_result_select_callback)
                for music in data:
                    url = hundred_shorten(music.url)
                    select.add_option(
                        label=hundred_shorten(music.title),
                        value=url, description=url
                    )
                    getattr(view, "data")[url] = music
                view.add_item(select)

                await reply(content=t(dict(
                    ja="{count}個が検索にヒットしました。\n選んでください。",
                    en="{count} items found in your search.\nPlease select one."
                ), ctx, count=len(data)), view=view)
                return

        # キューに追加する。
        if isinstance(data, Exception):
            raise data
        ext = {}
        if isinstance(data, tuple):
            self.now[ctx.guild].queue.extend(data[0])
            if data[1]:
                ext = {
                    "ja": "⚠️ 曲が多すぎたので何曲かは切り捨てられました。",
                    "en": "⚠️ Some songs were truncated because there were too many."
                }
        else:
            if self.now[ctx.guild].length >= max_result:
                await reply(content=t(dict(
                    ja="これ以上キューに音楽を追加することはできません。",
                    en="No more music can be added to the queue."
                ), ctx), view=None)
                return
            self.now[ctx.guild].queue.append(data)

        # 何も再生していないのなら再生する。
        embed = None
        now = self.now[ctx.guild].now
        assert now is not None
        if not self.now[ctx.guild].is_playing():
            await self.now[ctx.guild].play()
            embed = self.now[ctx.guild].queue[0].make_embed(duration_only=True)

        await reply(content=t(concat_text(
            {"ja": "📝 曲をキューに追加しました。", "en": "📝 Songs added to queue."}
                if embed is None else {"ja": "▶️ 再生します。", "en": "▶️ Playing"},
            ext, "\n"
        ), ctx), embed=embed or None, view=None)

    @command(
        description="Play music. YouTube, Soundcloud, and Nico Nico Douga are supported.",
        aliases=("p", "再生", "プレイ", "ぷれい")
    )
    @discord.app_commands.describe(query="The URL or playlist name of the video you wish to play.")
    @discord.app_commands.autocomplete(query=play_autocomplete)
    async def play(self, ctx: Cog.Context, *, query: str):
        await self._play(ctx, query)

    @check(make_ask_text("スキップ", "skip"))
    @command(
        description="Skip songs.",
        aliases=("skp", "スキップ", "パス", "ぱす", "すぷ", "とばす", "次", "つぎ")
    )
    async def skip(self, ctx: Cog.Context):
        self.now[ctx.guild].skip()
        return f"⏭ Skipped"

    @check(make_ask_text("ループ設定の変更", "change repeat setting"))
    @command(
        description="Change the song repeat setting.",
        aliases=("r", "loop", "lp", "リピート", "りぴ", "ループ", "るぷ")
    )
    @discord.app_commands.describe(
        mode="Repeat mode. `all` repeats all songs and `one` repeats one song. `none` is no repeat."
    )
    async def repeat(self, ctx: Cog.Context, mode: Literal["all", "one", "none"] | None = None):
        now = self.now[ctx.guild].loop(mode if mode is None else getattr(LoopMode, mode.upper()))
        if now == LoopMode.ALL:
            return "{}{}".format("🔁", t(dict(
                ja="全曲リピートにしました。", en="I put all the songs on repeat."
            ), ctx))
        elif now == LoopMode.ONE:
            return "{}{}".format("🔂", t(dict(
                ja="一曲リピートにしました。", en="I put one song on repeat."
            ), ctx))
        else:
            return "{}{}".format("➡️", t(dict(
                ja="リピート設定を無しにしました。", en="No repeat setting."
            ), ctx))

    @check(make_ask_text("音量の変更", "change volume"))
    @command(
        description="Change the volume.",
        aliases=("vol", "v", "音量", "おり")
    )
    @discord.app_commands.describe(volume="Volume in percent.")
    async def volume(self, ctx: Cog.Context, volume: float):
        self.now[ctx.guild].volume = volume / 100
        return f"🔊 Changed: {volume}%"

    @check(make_ask_text("シャッフル", "shuffle"))
    @command(
        description="Shuffle the songs in the queue.",
        aliases=("s", "random", "rd", "シャッフル", "ランダム", "しる")
    )
    async def shuffle(self, ctx: Cog.Context):
        self.now[ctx.guild].shuffle()
        return "🔀 Shuffled"

    @check(make_ask_text("一時停止", "pause"))
    @command(
        description="Pause the song. Or resume the song.",
        aliases=("ps", "ポーズ", "一時停止", "ぽず")
    )
    async def pause(self, ctx: Cog.Context):
        return "⏸ Paused" if self.now[ctx.guild].toggle_pause() else "▶️ Resumed"

    @check()
    @command(
        "now", description="Displays information about the currently playing music.",
        aliases=("playing", "現在", "今", "音楽", "曲", "おがく")
    )
    async def now_(self, ctx: Cog.Context):
        await ctx.reply(embed=self.now[ctx.guild].now.make_embed(True)) # type: ignore

    @check(make_ask_text("ストップ", "stop"))
    @command(
        description="Quits music playback.",
        aliases=("stp", "停止", "終了", "てし", "エンド", "バイバイ", "もう延々に", "会えないね")
    )
    async def stop(self, ctx: Cog.Context):
        self.now[ctx.guild].queue = self.now[ctx.guild].queue[:1]
        # もし音楽プレイヤー以外も使っている場合は、スキップで曲の再生を終了させるだけにする。
        if len(self.now[ctx.guild].mixer.now.sources) == 1: # type: ignore
            await self.bot.mixers.release(self.now[ctx.guild].mixer.vc.channel)
        else:
            self.now[ctx.guild].skip()
        del self.now[ctx.guild]
        return "⏹ Stopped"


async def setup(bot: RT) -> None:
    await bot.add_cog(MusicCog(bot))