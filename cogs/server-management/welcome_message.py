# RT - Welcome Message

from __future__ import annotations

from typing import NamedTuple, Literal

from discord.ext import commands
import discord

from orjson import loads

from core import Cog, RT, t, DatabaseManager, cursor

from rtlib.common import dumps
from rtutil.utils import ContentData, disable_content_json, is_json

from data import FORBIDDEN, CHANNEL_NOTFOUND

from .__init__ import FSPARENT


Mode = Literal["join", "leave"]
WelcomeData = NamedTuple("WelcomeData", (
    ("channel_id", int), ("mode", Mode), ("text", ContentData)
))
class DataManager(DatabaseManager):
    def __init__(self, cog: WelcomeMessage):
        self.cog = cog
        self.pool = self.cog.bot.pool

    async def prepare_table(self) -> None:
        "テーブルを用意します。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS WelcomeMessage (
                GuildId BIGINT, ChannelId BIGINT,
                Mode ENUM('join', 'leave'), Text JSON
            );"""
        )

    async def write(
        self, guild_id: int, channel_id: int,
        mode: Mode, data: ContentData | None
    ) -> None:
        "データを書き込みます。"
        if data is None:
            await cursor.execute(
                "DELETE FROM WelcomeMessage WHERE GuildId = %s AND Mode = %s;",
                (guild_id, mode)
            )
        else:
            if await self.read(guild_id, mode, cursor=cursor):
                await cursor.execute(
                    """UPDATE WelcomeMessage SET Text = %s, ChannelId = %s
                        WHERE GuildId = %s AND Mode = %s;""",
                    (dumps(data), guild_id, channel_id, mode)
                )
            else:
                await cursor.execute(
                    "INSERT INTO WelcomeMessage VALUES (%s, %s, %s, %s)",
                    (guild_id, channel_id, mode, dumps(data))
                )

    async def read(self, guild_id: int, mode: Mode, **_) -> WelcomeData | None:
        "データを読み込みます。"
        await cursor.execute(
            "SELECT * FROM WelcomeMessage WHERE GuildId = %s AND Mode = %s;",
            (guild_id, mode)
        )
        if row := await cursor.fetchone():
            return WelcomeData(row[1], row[2], loads(row[3]))

    async def clean(self) -> None:
        "データのお掃除をします。"
        await self.clean_data(cursor, "WelcomeMessage", "ChannelId")


class WelcomeSendEventContext(Cog.EventContext):
    "ウェルカムメッセージの送信のイベントコンテキストです。"

    channel: discord.TextChannel
    data: WelcomeData


class WelcomeMessage(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.command(
        fsparent=FSPARENT, aliases=(
            "to", "ようこそ", "ジャパリパーク", "今日も",
            "どったんばったん", "大騒ぎ", "うー", "がおー"
        ), description="Set the entry/exit message."
    )
    async def welcome(self, ctx: commands.Context, mode: Mode, *, text: str = ""):
        assert ctx.guild is not None and self.bot.user is not None
        async with ctx.typing():
            if text:
                await self.data.write(ctx.guild.id, ctx.channel.id, mode, loads(text)
                        if is_json(text) else ContentData(
                    content={"content": text}, author=self.bot.user.id, json=True
                ))
            else:
                await self.data.write(ctx.guild.id, ctx.channel.id, mode, None)
        await ctx.reply("Ok")

    (Cog.HelpCommand(welcome)
        .merge_headline(ja="入退出メッセージを設定します。")
        .set_description(ja="入退出メッセージを設定します。", en=welcome.description)
        .add_arg("mode", "Choice",
            ja="""入室または退出のどちらの時にメッセージを送るかです。
                `join` 入室
                `leave` 退出""",
            en="""The message is sent when you enter or leave a room.
                `join` enter a room
                `leave` leave""")
        .add_arg("text", "str",
            ja="""送信するメッセージです。
                `Get content`で取得したコードを使用することも可能です。
                未指定は設定解除とみなします。""",
            en="""The message to be sent.
                You can also use the code obtained with `Get content`.
                Undesignated is considered to be a de-setting."""))

    async def on_member(self, mode: Mode, member: discord.Member):
        data = await self.data.read(member.guild.id, mode)
        if data is not None:
            detail = ""
            if (channel := self.bot.get_channel(data.channel_id)) is not None:
                assert isinstance(channel, discord.TextChannel)
                try:
                    await channel.send(**disable_content_json(data.text)["content"])
                except discord.Forbidden:
                    detail = FORBIDDEN
            else:
                detail = CHANNEL_NOTFOUND
            self.bot.rtevent.dispatch("on_welcome_message_send", WelcomeSendEventContext(
                self.bot, member.guild, "ERROR" if detail else "SUCCESS",
                {"ja": "ウェルカムメッセージ", "en": "Welcome message"}, detail or {
                    "ja": f"送信チャンネルID：{data.channel_id}",
                    "en": f"Channel ID：{data.channel_id}"
                }, self.welcome, channel=channel, data=data
            ))

    @commands.Cog.listener()
    async def on_member_join_cooldown(self, member: discord.Member):
        await self.on_member("join", member)

    @commands.Cog.listener()
    async def on_member_remove_cooldown(self, member: discord.Member):
        await self.on_member("leave", member)


async def setup(bot: RT) -> None:
    await bot.add_cog(WelcomeMessage(bot))