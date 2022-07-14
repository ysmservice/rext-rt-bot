# RT - Welcome Message

from __future__ import annotations

from typing import NamedTuple, Literal

from discord.ext import commands
import discord

from core import Cog, RT, DatabaseManager, cursor

from rtutil.content_data import ContentData, disable_content_json, convert_content_json

from rtlib.common.json import dumps, loads

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
                await self.data.write(ctx.guild.id, ctx.channel.id, mode, convert_content_json(
                    text, self.bot.user.id
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
                未指定は設定解除とみなします。
                また、以下の文字を含めると右側にある文字列に交換されます。
                ```python
                !mb! Botを含まないサーバーの人数
                !us! Botを含むサーバーの人数
                !name! 新しいメンバーの名前
                !ment! 新しいメンバーのメンション
                ```""",
            en="""The message to be sent.
                You can also use the code obtained with `Get content`.
                Undesignated is considered to be a de-setting.
                Also, if you include the following characters, they will be replaced by the string on the right side
                ```python
                !mb! Number of people on the server not including the Bot.
                !us! Number of people on the server including the Bot.
                !name! New member's name.
                !ment! New member's mention
                ```"""))

    def _update_text(self, text: str, member: discord.Member) -> str:
        return text.replace("!ment!", member.mention).replace("!name!", member.display_name)

    async def on_member(self, mode: Mode, member: discord.Member):
        data = await self.data.read(member.guild.id, mode)
        if data is not None:
            detail = ""
            if (channel := self.bot.get_channel(data.channel_id)) is not None:
                assert isinstance(channel, discord.TextChannel)
                kwargs = disable_content_json(data.text)["content"]
                # もしメッセージ内容に`!bt!`などがあるなら、それに対応する数に交換する。
                if "content" in kwargs:
                    kwargs["content"] = self._update_text(
                        self.bot.cogs["ChannelStatus"]._update_text( # type: ignore
                            kwargs["content"], channel.guild
                        ), member
                    )
                try:
                    await channel.send(**kwargs)
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