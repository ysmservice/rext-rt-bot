# RT - GlobalChat

from typing import TypedDict, NamedTuple
from collections.abc import AsyncIterator

from collections import defaultdict

from asyncio import gather

import discord
from discord.ext import commands

from core import Cog, RT, t, DatabaseManager, cursor

from rtutil.utils import webhook_send

from rtlib.common.cacher import Cacher
from rtlib.common.json import dumps, loads

from data import FORBIDDEN

from .__init__ import FSPARENT


class Setting(TypedDict, total=False):
    "グローバルチャットの設定"
    password: str | None
class Data(NamedTuple):
    name: str
    author_id: int
    setting: Setting


class DataManager(DatabaseManager):
    "セーブデータを管理します"

    MAX_GLOBAL_CHAT_COUNT = 3
    MAX_CHANNEL_COUNT = 30

    def __init__(self, bot: RT):
        self.pool = bot.pool
        self.bot = bot
        self.caches: defaultdict[str, list[int]] = defaultdict(list)

    async def prepare_table(self) -> None:
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalChat (
                Name TEXT, AuthorId BIGINT, Setting JSON
            );"""
        )
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalChatMessage(
                Source BIGINT, ChannelId BIGINT PRIMARY KEY NOT NULL,
                MessageId BIGINT
            );"""
        )
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalChatChannel(
                Name TEXT, ChannelId BIGINT
            );"""
        )
        # キャッシュを用意する。
        async for row in self.fetchstep(cursor, "SELECT * FROM GlobalChatChannel;"):
            self.caches[row[0]].append(row[1])

    async def is_not_exists_with_error(self, name: str, **_) -> None:
        "`.is_exists`を実行して、既に存在する場合のみエラーを発生させます。"
        if await self.is_exists(name, cursor=cursor):
            raise Cog.BadRequest({
                "en": "This globalchat already exists.",
                "ja": "このグローバルチャットは既に存在しています。"
            })

    async def is_exists_with_error(self, name: str, **_) -> None:
        "`.is_exists`を実行して、既に存在しない場合のみエラーを発生させます。"
        if not await self.is_exists(name, cursor=cursor):
            raise Cog.BadRequest({
                "en": "This globalchat is not exists.",
                "ja": "このグローバルチャットは存在しません。"
            })

    async def is_connected_with_error(self, channel_id: int, **_) -> None:
        "`.is_connected`を実行して、既に接続している場合はエラーを発生させます。"
        if await self.is_connected(channel_id, cursor=cursor):
            raise Cog.BadRequest({
                "en": "You are already connected to this globalchat.",
                "ja": "既にこのグローバルチャットに接続しています。"
            })

    async def connect(self, name: str, channel_id: int) -> None:
        "グローバルチャットに接続します。"
        await self.is_exists_with_error(name, cursor=cursor)
        await self.is_connected_with_error(channel_id, cursor=cursor)
        await cursor.execute(
            "INSERT INTO GlobalChatChannel VALUES (%s, %s);",
            (name, channel_id)
        )
        self.caches[name].append(channel_id)

    async def create(
        self, name: str, author_id: int,
        channel_id: int, setting: Setting
    ) -> None:
        "主にグローバルチャットを作るために使います。"
        await self.is_not_exists_with_error(name, cursor=cursor)
        # グローバルチャットを作成した人が、最大作成可能個数分既にグローバルチャットを作っているのなら、エラーを起こす。
        await cursor.execute(
            "SELECT COUNT(AuthorId) FROM GlobalChat WHERE AuthorId = %s;",
            (author_id,)
        )
        if (await cursor.fetchone())[0] > self.MAX_GLOBAL_CHAT_COUNT:
            raise Cog.BadRequest({
                "ja": "あなたはグローバルチャットを作りすぎです。\nそのためグローバルチャットを作ることができません。",
                "en": "You are creating too much global chat.\nYou cannot create a global chat because of that."
            })
        # 接続数が最大接続数になっている場合は拒否する。
        if len(self.caches[name]) >= 30:
            raise Cog.BadRequest({
                "ja": "これ以上このグローバルチャットにチャンネルを接続することができません。",
                "en": "No more channels can be connected for this global chat."
            })
        # グローバルチャットの作成を行う。
        await cursor.execute(
            "INSERT INTO GlobalChat VALUES (%s, %s, %s);",
            (name, author_id, dumps(setting))
        )
        await cursor.execute(
            "INSERT INTO GlobalChatChannel VALUES (%s, %s);",
            (name, channel_id)
        )
        self.caches[name].append(channel_id)

    async def is_connected(self, channel_id: int, **_) -> bool:
        "これはすでに接続されているか確認するものです。"
        return (await self.get_name(channel_id, cursor=cursor)) is not None

    async def is_exists(self, name: str, **_) -> bool:
        "すでにグローバルチャットが存在するか確認します。"
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE Name = %s LIMIT 1;",
            (name,)
        )
        return bool(await cursor.fetchone())

    async def check_password(self, name: str, password: str | None) -> bool | None:
        "パスワードを確認します。"
        await cursor.execute(
            "SELECT Setting FROM GlobalChat WHERE Name = %s LIMIT 1;",
            (name,)
        )
        if row := await cursor.fetchone():
            return loads(row[0])["password"] == password

    async def get_channel_ids(self, name: str, **_) -> AsyncIterator[int]:
        "グローバルチャットに接続しているチャンネルを名前使って全部取得します。"
        async for (channel_id,) in self.fetchstep(
            cursor, "SELECT ChannelId FROM GlobalChatChannel WHERE Name = %s;", (name,)
        ):
            yield channel_id

    async def get_name(self, channel_id: int, **_) -> str | None:
        "チャンネルから接続しているグローバルチャット名を取得します。"
        await cursor.execute(
            "SELECT Name FROM GlobalChatChannel WHERE ChannelId = %s LIMIT 1;",
            (channel_id,)
        )
        if row := await cursor.fetchone():
            return row[0]

    async def disconnect(self, channel_id: int, **_) -> None:
        "グローバルチャットから接続をやめます。"
        if (name := await self.get_name(channel_id, cursor=cursor)) is None:
            raise Cog.BadRequest({
                "ja": "そのチャンネルは接続されていません。",
                "en": "That channel is not connected."
            })
        await cursor.execute(
            "DELETE FROM GlobalChatChannel WHERE ChannelId = %s;",
            (channel_id,)
        )
        self.caches[name].remove(channel_id)

    async def insert_message(self, source: int, channel_id: int, message_id: int) -> None:
        "メッセージを保存します。"
        await cursor.execute(
            "INSERT INTO GlobalChatMessage VALUES (%s, %s, %s);",
            (source, channel_id, message_id)
        )

    async def get_setting(self, name: str) -> Data:
        "グローバルチャットを取得します。"
        await cursor.execute(
            "SELECT * FROM GlobalChat WHERE Name = %s LIMIT 1;",
            (name,)
        )
        if row := await cursor.fetchone():
            return Data(*row)
        raise Cog.BadRequest({
            "en": "That globalchat does not exist.",
            "ja": "そのグローバルチャットは存在しません。"
        })


class GlobalChatEventContext(Cog.EventContext):
    "グローバルチャットに送信されたメッセージを、チャンネルに送信する際に発生するイベントのコンテキストです。"

    channel: discord.TextChannel
    message: discord.Message


class GlobalChat(Cog):
    "グローバルチャットのコグです。"

    def __init__(self, bot: RT):
        self.bot = bot
        self.pool = self.bot.pool
        self.data = DataManager(bot)
        self.cooldowns: Cacher[tuple[int, int], int] = self.bot.cachers.acquire(10.0)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.group(
        description="The command of globalchat.", fsparent=FSPARENT,
        aliases=("gc", "gchat", "グローバルチャット", "ぐろちゃ")
    )
    async def globalchat(self, ctx):
        await self.group_index(ctx)

    async def check_text_channel(self, ctx: commands.Context) -> None:
        "テキストチャンネル以外のコンテキストの場合はエラーが発生します。"
        if not isinstance(ctx.channel, discord.TextChannel):
            raise Cog.BadRequest({
                "ja": "グローバルチャットに接続させるチャンネルはテキストチャンネルでなければいけません。",
                "en": "The channel to be connected to global chat must be a text channel."
            })

    @globalchat.command(description="Create globalchat.", aliases=("make", "add", "作成")
    )
    @discord.app_commands.describe(name="Global chat name", password="Password")
    async def create(self, ctx, name: str, *, password: str | None = None):
        await self.check_text_channel(ctx)
        await self.data.create(name, ctx.author.id, ctx.channel.id, {
            "password": password
        })
        await ctx.reply(t(dict(en="Created", ja="作成しました。"), ctx))

    @globalchat.command(
        description="Connect to global chat.",
        aliases=("join", "参加", "c", "さか")
    )
    @discord.app_commands.describe(name="Global chat name", password="Password")
    async def connect(self, ctx, name: str, *, password: str | None = None):
        await self.check_text_channel(ctx)
        if not await self.data.check_password(name, password):
            return await ctx.reply(t(dict(
                en="Wrong password",
                ja="パスワードが間違っています。"
            ), ctx))
        await self.data.connect(name, ctx.channel.id)
        await ctx.reply(t(dict(en="Connected", ja="接続しました。"), ctx))

    @globalchat.command(
        description="Disconnect from globalchat.",
        aliases=("remove", "rm", "退出", "leave")
    )
    async def disconnect(self, ctx):
        await self.data.disconnect(ctx.channel.id)
        await ctx.reply(t(dict(
            ja="グローバルチャットから退出しました",
            en="Leave from globalchat"
        ), ctx))

    _help = Cog.HelpCommand(globalchat).merge_description("headline", ja="グローバルチャット関連です。")
    _help.add_sub(Cog.HelpCommand(create)
        .merge_description("headline", ja="グローバルチャットを作成します。")
        .add_arg("name", "str", "Optional",
            ja="グローバルチャット名", en="Globalchat name")
        .add_arg("password", "str", "Optional",
            ja="パスワード", en="Password"))
    _help.add_sub(Cog.HelpCommand(connect)
        .merge_description("headline", ja="グローバルチャットに接続します。")
        .add_arg("name", "str", "Optional",
            ja="グローバルチャット名", en="GlobalChat name")
        .add_arg("password", "str", "Optional",
            ja="パスワード", en="Password"))
    _help.add_sub(Cog.HelpCommand(disconnect).merge_description(
        "headline", ja="グローバルチャットから退出します。"))
    del _help

    @Cog.listener("on_message")
    async def on_message(self, message: discord.Message):
        if message.author.bot or isinstance(message.author, discord.User):
            return

        # グローバルチャットに接続しているチャンネルかどうかをチェックする。
        for name, channel_ids in self.data.caches.items():
            if message.channel.id in channel_ids:
                break
        else:
            return
        # クールダウンでメッセージを拒否すべきかを確認する。
        if (message.channel.id, message.author.id) in self.cooldowns:
            if self.cooldowns[(message.channel.id, message.author.id)] < 4:
                await gather(
                    message.delete(), message.author.send(t(dict(
                        ja="クールダウン中なので送れません。グローバルチャットは10秒のクールダウンが適用されています。"
                            "なお、このメッセージは三回連続でクールダウンを無視した後は表示されませんので、しっかり十秒数えてから送るようにしてください。"
                            "あなたが送ろうとしたメッセージ：\n{content}",
                        en="It is on cooldown and cannot be sent. Global Chat is on a 10 second cooldown."
                            "Note that this message will not appear after ignoring the cooldown three times in a row, so be sure to count ten seconds before sending it."
                            "The message you tried to send:\n{content}"
                    ), message.author, content=message.content))
                )
        else:
            self.cooldowns[(message.channel.id, message.author.id)] = 0
        self.cooldowns[(message.channel.id, message.author.id)] += 1

        # メッセージの送信を行う。
        for channel_id in self.data.caches[name]:
            if message.channel.id == channel_id:
                continue

            # チャンネルの取得を行う。
            channel = await self.bot.search_channel(channel_id)
            assert isinstance(channel, discord.TextChannel)
            if channel is None:
                await self.data.disconnect(channel_id, cursor=cursor)
                continue

            # 送信を行う。
            error = None
            try:
                await webhook_send(
                    channel, message.author, message.clean_content, files=[
                        await attachment.to_file()
                        for attachment in message.attachments
                    ]
                )
            except discord.Forbidden:
                error = FORBIDDEN
            except Exception:
                ...

            self.bot.rtevent.dispatch("on_global_chat_message", GlobalChatEventContext(
                self.bot, channel.guild, error, {
                    "ja": "グローバルチャットからのメッセージの襲来",
                    "en": "An assault of messages from global chat"
                }, self.text_format({
                    "ja": "送信対象：{name}", "en": "Target: {name}"
                }, name=self.name_and_id(channel)), self.globalchat, error,
                channel=channel, message=message
            ))


async def setup(bot: RT) -> None:
    await bot.add_cog(GlobalChat(bot))