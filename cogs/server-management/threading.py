# RT - Threading

from __future__ import annotations

from typing import Any, NamedTuple, TypeAlias, Literal
from collections.abc import Callable, Iterator

from discord.ext import commands
import discord

from core import Cog, RT, t, DatabaseManager, cursor
from core.types_ import Text

from rtlib.common.cacher import Cacher

from data import FORBIDDEN, LIST_ALIASES, NO_MORE_SETTING, ROLE_NOTFOUND, TOGGLE_ALIASES

from .__init__ import FSPARENT


Mode: TypeAlias = Literal["keeper", "notification"]
Data = NamedTuple("Data", (("channel_id", int), ("mode", Mode), ("extras", Any)))
class DataManager(DatabaseManager):
    "スレッド管理コマンドのthreading用のセーブデータ管理用クラスです。"

    def __init__(self, cog: Threading):
        self.cog = cog
        self.pool = self.cog.bot.pool

    async def prepare_table(self) -> None:
        "テーブルを作ります。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS ThreadingToggleFeatures (
                GuildId BIGINT, ChannelId BIGINT,
                Mode ENUM('keeper', 'notification'),
                Extras TEXT
            );"""
        )

    async def read(self, channel_id: int, mode: Mode, **_) -> Data | None:
        "スレッドのtoggle系機能のデータを取得します。"
        await cursor.execute(
            """SELECT ChannelId, Mode, Extras FROM ThreadingToggleFeatures
                WHERE ChannelId = %s AND Mode = %s LIMIT 1;""",
            (channel_id, mode)
        )
        if (row := await cursor.fetchone()) is not None:
            return Data(*row)

    async def read_all(self, guild_id: int, mode: Mode, **_) -> Iterator[Data]:
        "スレッドアーカイブ防止の監視対象のチャンネルIDの集合を取得します。"
        await cursor.execute(
            """SELECT ChannelId, Mode, Extras FROM ThreadingToggleFeatures
                WHERE GuildId = %s AND Mode = %s;""",
            (guild_id, mode)
        )
        return map(lambda x: Data(*x), await cursor.fetchall())

    MAX_MONITORS = 15

    async def toggle(self, guild_id: int, channel_id: int, mode: Mode, extras: str) -> None:
        "スレッドのアーカイブ防止の監視のON/OFFの切り替えをします。"
        if len(rows := set(await self.read_all(guild_id, mode, cursor=cursor))) \
                >= self.MAX_MONITORS:
            raise Cog.BadRequest(NO_MORE_SETTING)
        if any(row.channel_id == channel_id for row in rows):
            await cursor.execute(
                "DELETE FROM ThreadingToggleFeatures WHERE ChannelId = %s AND Mode = %s;",
                (channel_id, mode)
            )
        else:
            await cursor.execute(
                "INSERT INTO ThreadingToggleFeatures VALUES (%s, %s, %s, %s);",
                (guild_id, channel_id, mode, extras)
            )


class ThreadingAutoUnArchiveEventContext(Cog.EventContext):
    "スレッドのアーカイブの自動解除時のイベントコンテキストです。"

    thread: discord.Thread
class ThreadingNotificationEventContext(Cog.EventContext):
    "スレッドの作成/アーカイブ通知のイベントコンテキストです。"

    thread: discord.Thread
    role: discord.Role | None


class Threading(Cog):
    "スレッド管理コマンドのthreadingのコグです。"

    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)
        self.caches: Cacher[int, None] = self.bot.cachers.acquire(5)

    async def cog_load(self):
        await self.data.prepare_table()

    async def _toggle(
        self, ctx: commands.Context,
        channel: discord.TextChannel | None,
        mode: Mode, extras: str
    ) -> None:
        # toggle系の設定のON/OFFをします。
        async with ctx.typing():
            assert ctx.guild is not None
            await self.data.toggle(ctx.guild.id, (channel or ctx.channel).id, mode, extras)
        await ctx.reply("Ok")

    async def _reply_list(
        self, ctx: commands.Context, mode: Mode, title: str,
        extras: Callable[[Data], str] = lambda _: ""
    ) -> None:
        # toggle系の設定リストを返信します。
        await ctx.typing()
        assert ctx.guild is not None
        await ctx.reply(embed=Cog.Embed(title=f"Thread {title}", description=", ".join(
            f"<#{data.channel_id}>{extras(data)}"
            for data in await self.data.read_all(ctx.guild.id, mode)
        )))

    @commands.group(
        aliases=("thm", "thread_manager", "スレッド", "スレッディング", "スレッドマネージャー", "スレ"),
        description="The command for controling threads.", fsparent=FSPARENT
    )
    async def threading(self, ctx: commands.Context):
        await self.group_index(ctx)

    @threading.group(
        aliases=("kp", "monitor", "unarchiver", "監視", "キーパー"),
        description="Thread Archive Releaser"
    )
    async def keeper(self, ctx: commands.Context):
        await self.group_index(ctx)

    @keeper.command("toggle", aliases=TOGGLE_ALIASES, description="Turns THREADKEEPER on/off.")
    @discord.app_commands.describe(channel=(_c_d := "Target channel"))
    async def toggle_keeper(
        self, ctx: commands.Context, *,
        channel: discord.TextChannel | None = None
    ):
        await self._toggle(ctx, channel, "keeper", "")

    @keeper.command(
        "list", aliases=LIST_ALIASES,
        description="Displays a list of channels with threadkeeper enabled."
    )
    async def list_keeper(self, ctx: commands.Context):
        await self._reply_list(ctx, "keeper", "Keeper")

    @threading.group(
        aliases=("notice", "nof", "通知", "お知らせ"),
        description="Thread creation and archive notification."
    )
    async def notification(self, ctx: commands.Context):
        await self.group_index(ctx)

    @notification.command(
        "toggle", aliases=TOGGLE_ALIASES,
        description="Set up event notifications for threads."
    )
    @discord.app_commands.describe(
        role=(_r_d := "The role that will be used to mention."), channel=_c_d
    )
    async def toggle_notification(
        self, ctx: commands.Context, role: discord.Role | None = None, *,
        channel: discord.TextChannel | None = None,
    ):
        await self._toggle(ctx, channel, "notification", "0" if role is None else str(role.id))

    @notification.command(
        "list", aliases=LIST_ALIASES,
        description="Displays a list of channels for which thread event notifications are set."
    )
    async def list_notification(self, ctx: commands.Context):
        await self._reply_list(
            ctx, "notification", "Notification",
            lambda data: "" if data.extras == "0" else f": <@&{data.extras}>"
        )

    _THREAD = {
        "ja": "スレッド：{name}", "en": "Thread: {name}"
    }

    async def _process_notification(self, thread: discord.Thread, text: Text) -> None:
        # スレッドの通知の処理を行います。
        # キャッシュの状況を確認する。
        if thread.guild.id in self.caches:
            del self.caches[thread.guild.id]
            return
        self.caches[thread.guild.id] = None

        if (data := await self.data.read(thread.parent_id, "notification")) is not None:
            error = None
            # 通知メンション用のロールの取得を行う。
            if data.extras == "0":
                role = None
            else:
                role = thread.guild.get_role(int(data.extras))
                error = ROLE_NOTFOUND
            if error is not None:
                # 通知の送信を行う。
                try:
                    await thread.send(t(dict(text), thread.guild,
                    mention="" if role is None else f"{role.mention}, "))
                except discord.Forbidden:
                    error = FORBIDDEN
            self.bot.rtevent.dispatch(
                "on_threading_notification", ThreadingNotificationEventContext(
                    self.bot, thread.guild, self.detail_or(error), {
                        "ja": "Threading: 通知", "en": "Threading: Notification"
                    }, self.text_format(self._THREAD, name=self.name_and_id(thread)),
                    self.threading, (error,)
                )
            )

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        if after.parent is not None and after.archived and not after.locked \
                and await self.data.read(after.parent.id, "keeper"):
            # 自動ロックされたならロックを解除する。
            detail = ""
            try:
                await after.edit(archived=False)
            except discord.Forbidden:
                detail = FORBIDDEN
            self.bot.rtevent.dispatch(
                "on_threading_auto_unarchive", ThreadingAutoUnArchiveEventContext(
                self.bot, after.guild, self.detail_or(detail), {
                    "ja": "Threading: 自動アーカイブ解除", "en": "Threading: Auto unarchive"
                }, detail or self.text_format(self._THREAD, name=self.name_and_id(after)),
                self.threading
            ))

        if (before.archived and not after.archived) or (before.locked and not after.locked):
            # アーカイブ解除時には通知を行う。
            await self._process_notification(after, {
                "ja": "{mention}アーカイブが解除されました。",
                "en": "{mention}The archive has been released."
            })


async def setup(bot: RT) -> None:
    await bot.add_cog(Threading(bot))