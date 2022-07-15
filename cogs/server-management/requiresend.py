# RT - Require Sent

from __future__ import annotations

from collections.abc import AsyncIterator

from dataclasses import dataclass
from time import time

from discord.ext import commands, tasks
import discord

from orjson import loads, dumps

from core import RT, Cog, t, DatabaseManager, cursor

from rtlib.common.cacher import Cacher
from rtutil.utils import unwrap_or

from data import (
    SETTING_NOTFOUND, ALREADY_NO_SETTING, TOO_LARGE_NUMBER, FORBIDDEN,
    ADD_ALIASES, REMOVE_ALIASES, LIST_ALIASES
)

from .__init__ import FSPARENT


@dataclass
class Caches:
    "複数のキャッシュ一つにまとめるためのクラスです。"

    settings: Cacher[int, dict[int, float]]
    queues: Cacher[int, dict[int, list[int]]]


class RequireSentKickEventContext(Cog.EventContext):
    "RequireSentによるキックが執行された際のイベントのためのContextです。"

    member: discord.Member
    channel_id: int
    channel_name: str | None


class DataManager(DatabaseManager):

    MAX_CHANNELS = 10

    def __init__(self, cog: RequireSent):
        self.cog = cog
        self.pool = self.cog.bot.pool
        self.caches = Caches(*(
            self.cog.bot.cachers.acquire(1800.0, dict) for _ in "__"
        ))

    async def prepare_table(self):
        "テーブルを作ります。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS RequireSent (
                GuildId BIGINT, ChannelId BIGINT, Deadline DOUBLE
            );"""
        )
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS RequireSentQueue (
                GuildId BIGINT, UserId BIGINT, Done JSON
            );"""
        )

    async def get(self, guild_id: int, **_) -> dict[int, float]:
        "サーバーの設定を読み込みます。"
        await cursor.execute(
            "SELECT ChannelId, Deadline FROM RequireSent WHERE GuildId = %s;",
            (guild_id,)
        )
        self.caches.settings[guild_id] = {row[0]: row[1] for row in await cursor.fetchall() if row}
        return self.caches.settings[guild_id]

    async def add(self, guild_id: int, channel_id: int, deadline: float) -> None:
        "設定を追加します。"
        if channel_id in (channel_ids := await self.get(guild_id, cursor=cursor)):
            raise Cog.reply_error.BadRequest({
                "ja": "そのチャンネルは既に設定されています。",
                "en": "That channel is already set up."
            })
        if len(channel_ids) >= self.MAX_CHANNELS:
            raise Cog.reply_error.BadRequest(ALREADY_NO_SETTING)
        await cursor.execute(
            "INSERT INTO RequireSent VALUES (%s, %s, %s);",
            (guild_id, channel_id, deadline)
        )
        if guild_id in self.caches.settings:
            self.caches.settings[guild_id][channel_id] = deadline

    async def remove(self, guild_id: int, channel_id: int) -> None:
        "設定を削除します。"
        if channel_id not in await self.get(guild_id, cursor=cursor):
            raise Cog.reply_error.BadRequest(SETTING_NOTFOUND)
        await cursor.execute(
            "DELETE FROM RequireSent WHERE GuildId = %s;",
            (guild_id,)
        )
        if guild_id in self.caches.settings and channel_id in self.caches.settings[guild_id]:
            del self.caches.settings[guild_id][channel_id]

    async def clear(self, guild_id: int, **_) -> None:
        "指定されたサーバーの設定を全部消します。"
        await cursor.execute("DELETE FROM RequireSent WHERE GuildId = %s;", (guild_id,))
        await cursor.execute("DELETE FROM RequireSentQueue WHERE GuildId = %s;", (guild_id,))

    def check_exists_both(self, guild_id: int, user_id: int) -> bool:
        "指定されたギルドIDとユーザーIDのキューがあるかをチェックします。"
        return guild_id in self.caches.queues and user_id in self.caches.queues[guild_id]

    async def delete_queue(self, guild_id: int, user_id: int, **_) -> None:
        "キューを削除します。"
        await cursor.execute(
            "DELETE FROM RequireSentQueue WHERE GuildId = %s AND UserId = %s;",
            (guild_id, user_id)
        )
        if self.check_exists_both(guild_id, user_id):
            del self.caches.queues[guild_id][user_id]

    async def set_queue(self, guild_id: int, user_id: int, done: list[int], **_) -> None:
        "RequireSentチャンネルのキューを設定か更新または削除します。"
        if all(channel_id in done for channel_id in await self.get(guild_id, cursor=cursor)):
            await self.delete_queue(guild_id, user_id, cursor=cursor)
            if self.check_exists_both(guild_id, user_id):
                del self.caches.queues[guild_id][user_id]
        else:
            await cursor.execute(
                "SELECT UserId FROM RequireSentQueue WHERE GuildId = %s AND UserId = %s;",
                (guild_id, user_id)
            )
            if await cursor.fetchone():
                await cursor.execute(
                    "UPDATE RequireSentQueue SET Done = %s WHERE GuildId = %s AND UserId = %s;",
                    (dumps(done).decode(), guild_id, user_id)
                )
            else:
                await cursor.execute(
                    "INSERT INTO RequireSentQueue VALUES (%s, %s, %s);",
                    (guild_id, user_id, dumps(done).decode())
                )
            if guild_id not in self.caches.queues:
                self.caches.queues[guild_id][user_id] = done

    async def get_queues(self, guild_id: int, **_) -> dict[int, list[int]]:
        "指定されたサーバーのキューを全て取得します。"
        if guild_id not in self.caches.queues:
            await cursor.execute(
                "SELECT UserId, Done FROM RequireSentQueue WHERE GuildId = %s;",
                (guild_id,)
            )
            self.caches.queues[guild_id] = {
                row[0]: loads(row[1]) for row in await cursor.fetchall()
            }
        return self.caches.queues[guild_id]

    async def get_all_queues(self, **_) -> AsyncIterator[tuple[int, int, list[int]]]:
        "全てのキューをサーバーづつ取得して返すイテレーターを返します。"
        async for row in self.fetchstep(cursor, "SELECT * FROM RequireSentQueue;"):
            yield row[:-1] + (loads(row[-1]),)

    SUBJECT = {"ja": "RequireSent キック", "en": "RequireSent Kick"}

    async def process_queues(self) -> None:
        "キューの処理をします。"
        guild, data, now = None, None, time()
        async for row in self.get_all_queues(cursor=cursor):
            if guild is None or guild.id != row[0]:
                guild = await self.cog.bot.search_guild(row[0])
            if guild is None:
                continue
            else:
                data = await self.get(row[0], cursor=cursor)
            if (member := await self.cog.bot.search_member(guild, row[1])) is None \
                    or member.joined_at is None:
                await self.delete_queue(*row[:2])
                continue
            # キューのメンバーが、RequireSentが設定されているチャンネルに、メッセージを送っていないまま放置している場合は、キックを行う。
            i = False
            for channel_id, deadline in filter(lambda x: x[0] not in row[2], data.items()): # type: ignore
                i = True
                if now - member.joined_at.timestamp() > deadline:
                    channel = await self.cog.bot.search_channel_from_guild(guild, channel_id)
                    reason = t(dict(
                        ja="RequireSentが設定されているチャンネルにメッセージを送信しなかった。\nチャンネル：{channel}" \
                            "\nメンバー：{member}",
                        en="The message was not sent to the channel where RequireSent is set.\nChannel: {channel}" \
                            "\nMember: {member}"
                    ), guild, channel=unwrap_or(channel, "name", channel_id),
                    member=self.cog.name_and_id(member))
                    ctx = RequireSentKickEventContext(
                        self.cog.bot, guild, subject=self.SUBJECT, detail=reason,
                        feature=self.cog.requiresent, member=member, channel_id=channel_id,
                        channel_name=unwrap_or(channel, "name")
                    )
                    # Byeする。
                    try:
                        await member.kick(reason=reason)
                    except discord.Forbidden:
                        ctx.detail = t(FORBIDDEN, guild)
                    finally:
                        await self.delete_queue(*row[:2])
                    self.cog.bot.rtevent.dispatch("on_requiresent", ctx)
                    break
            if not i:
                # もし全部送信したのならキューを消す。
                await self.delete_queue(*row[:2])

    async def clean(self) -> None:
        "掃除をします。"
        async for row in self.fetchstep(cursor, "SELECT * FROM RequireSent;"):
            if not await self.cog.bot.exists("guild", row[0]):
                await cursor.execute(
                    "DELETE FROM RequireSent WHERE GuildId = %s;",
                    row[:1]
                )
            elif await self.cog.bot.exists("channel", row[1]):
                await cursor.execute(
                    "DELETE FROM RequireSent WHERE ChannelId = %s;",
                    (row[1],)
                )
        await self.cog.bot.clean(cursor, "RequireSentQueue", "GuildId")


class RequireSent(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)
        self.checked: Cacher[tuple[int, int], bool] = self.bot.cachers.acquire(10.0)

    async def cog_load(self):
        await self.data.prepare_table()
        self.check_queues.start()

    async def cog_unload(self):
        self.check_queues.cancel()

    @tasks.loop(seconds=10)
    async def check_queues(self):
        await self.data.process_queues()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.bot and await self.data.get(member.guild.id):
            if self.checked.get((member.guild.id, member.id), False):
                return
            self.checked[(member.guild.id, member.id)] = True
            # RequireSentのチェック対象になるようにキューを追加する。
            await self.data.set_queue(member.guild.id, member.id, [])

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild \
                or message.type == discord.MessageType.new_member:
            return
        if data := await self.data.get(message.guild.id):
            if message.channel.id in data:
                done = (await self.data.get_queues(message.guild.id)).get(message.author.id)
                if done is not None:
                    done.append(message.channel.id)
                    await self.data.set_queue(message.guild.id, message.author.id, done)

    @commands.group(
        aliases=("入力必須", "rst"), fsparent=FSPARENT,
        description="Set required channel for sending a message when a member joined."
    )
    @commands.guild_only()
    async def requiresent(self, ctx: commands.Context):
        await self.group_index(ctx)

    REQUIRESENT_HELP = (Cog.HelpCommand(requiresent)
        .merge_headline(ja="入室時にメッセージを送信しなければならないチャンネルを設定します。")
        .set_description(
            ja="""メンバーが入室時にメッセージを送信しなければキックされるチャンネルを設定します。
                自己紹介チャンネル等に設定すると良いです。
                ここではこのようなチャンネルのことをRequireSentと呼びます。""",
            en="""Set up a channel where members must send a message when they enter a room or they will be kicked.
                You can set this to the self-introduction channel, etc.
                Here, such a channel is called RequireSent."""
        )
        .set_extra("Notes",
            ja="""参加者のメッセージを送信しているかしていないかをチェックするのは十秒づつ行われます。
                ですので、十秒程本来より遅れてキックされることがあります。""",
            en="""Checking whether or not a participant's message has been sent is done ten seconds at a time.
                Therefore, it may kick in 10 seconds later than it should."""))

    @requiresent.command(
        aliases=ADD_ALIASES,
        description="Sets the RequireSent channel"
    )
    @discord.app_commands.describe(
        deadline=(deadline_d := "It is how many seconds is the kick if the message is left without being sent."),
        channel=(channel_d := "The channel on which the message must be sent.")
    )
    async def add(self, ctx: commands.Context, deadline: float, *, channel: discord.TextChannel):
        await ctx.typing()
        if deadline > 259200:
            raise Cog.reply_error.BadRequest(TOO_LARGE_NUMBER)
        assert ctx.guild is not None
        await self.data.add(ctx.guild.id, channel.id, deadline)
        await ctx.reply("Ok")

    REQUIRESENT_HELP.add_sub(Cog.HelpCommand(add)
        .set_description(
            ja="RequireSentチャンネルを設定します。",
            en=add.description
        )
        .add_arg("deadline", "float",
            ja="何秒間送信されずに放置されたらキックをするかです。",
            en=deadline_d)
        .add_arg("channel", "TextChannel",
            ja="メッセージを送信しなければならないチャンネルです。",
            en=channel_d)
        .set_extra("Extras",
            ja="引数の`deadline`は三日の`259200`が最大です。",
            en="The `deadline` argument has a maximum of `259200` on the third day."))
    del deadline_d

    @requiresent.command(
        aliases=REMOVE_ALIASES,
        description="Cancel the RequireSent setting."
    )
    @discord.app_commands.describe(
        channel=(channel_d := "Channel to cancel setting.")
    )
    async def remove(self, ctx: commands.Context, *, channel: discord.TextChannel):
        await ctx.typing()
        assert ctx.guild is not None
        await self.data.remove(ctx.guild.id, channel.id)
        await ctx.reply("Ok")

    REQUIRESENT_HELP.add_sub(Cog.HelpCommand(remove)
        .set_description(
            ja="RequireSentチャンネルの設定を削除します。",
            en=remove.description
        )
        .add_arg("channel", "TextChannel",
            ja="対象のチャンネル", en="Target channel"))

    @requiresent.command(
        "list", aliases=LIST_ALIASES,
        description="Displays a list of RequireSent channels that have been set."
    )
    async def list_(self, ctx: commands.Context):
        await ctx.typing()
        assert ctx.guild is not None
        await ctx.reply("\n".join(
            f"{unwrap_or(ctx.guild.get_channel(cid), 'mention', cid)}: `{deadline}`"
            for cid, deadline in (await self.data.get(ctx.guild.id)).items()
        ))

    REQUIRESENT_HELP.add_sub(Cog.HelpCommand(list_)
        .set_description(
            ja="設定されているRequireSentのチャンネルのリストを表示します。",
            en=list_.description
        ))


async def setup(bot):
    await bot.add_cog(RequireSent(bot))