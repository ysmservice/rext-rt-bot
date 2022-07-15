# RT - RTA

from __future__ import annotations

from typing import Optional

from discord.ext import commands
from discord import app_commands
import discord

from datetime import datetime, timezone
from time import time

from core.types_ import Channel
from core import RT, Cog, t, DatabaseManager, cursor

from rtlib.common.cacher import Cacher

from data import FORBIDDEN


class DataManager(DatabaseManager):
    def __init__(self, bot: RT):
        self.pool, self.bot = bot.pool, bot

    async def get(self, guild_id: int, **_) -> Optional[Channel]:
        "RTAの設定を読み込みます。"
        await cursor.execute(
            "SELECT ChannelId FROM rta WHERE GuildId = %s;",
            (guild_id,)
        )
        if row := await cursor.fetchone():
            return self.bot.get_channel(row[0])

    async def prepare_table(self):
        "テーブルを用意します。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS rta (
                GuildId BIGINT PRIMARY KEY NOT NULL, ChannelId BIGINT
            );"""
        )

    async def set(self, guild_id: int, channel_id: int | None) -> bool:
        "RTAを設定します。"
        if channel_id is None or (
            (channel := await self.get(guild_id, cursor=cursor)) is not None
            and channel.id == channel_id
        ):
            await cursor.execute(
                "DELETE FROM rta WHERE GuildId = %s;",
                (guild_id,)
            )
            return False
        else:
            await cursor.execute(
                """INSERT INTO rta VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE ChannelId = %s;""",
                (guild_id, channel_id, channel_id)
            )
            return True

    async def clean(self) -> None:
        "いらないセーブデータを消します。"
        await cursor.execute("SELECT * FROM rta;")
        async for guild_id, channel_id in self.fetchstep(cursor, "SELECT * FROM rta;"):
            if not await self.bot.exists("guild", guild_id):
                await cursor.execute(
                    "DELETE FROM rta WHERE GuildId = %s;", (guild_id,)
                )
            elif not await self.bot.exists("channel", channel_id):
                await cursor.execute(
                    "DELETE FROM rta WHERE ChannelId = %s;", (channel_id,)
                )


class ImmediateExitContext(Cog.EventContext):
    member: discord.Member
    seconds: float


IMMEDIATE_EXIT = dict(ja="即抜けRTA", en="Immediate Quit")
class RTA(Cog):
    def __init__(self, bot: RT):
        self.data, self.bot = DataManager(bot), bot
        self.sended: Cacher[str, float] = bot.cachers.acquire(60)

    async def cog_load(self):
        await self.data.prepare_table()

    FSPARENT = Cog.get_fsparent(cog_load)

    @commands.group(description="Immediate Quit RTA Feature", fsparent=FSPARENT)
    @commands.has_guild_permissions(administrator=True)
    @commands.guild_only()
    async def rta(self, ctx: commands.Context):
        if not ctx.invoked_subcommand:
            await ctx.reply(self.ERRORS["WRONG_WAY"](ctx))

    @rta.command(description="Setup a Immediate Quit RTA")
    @app_commands.describe(channel="Notify target channel")
    async def setup(
        self, ctx: commands.Context, *,
        channel: Optional[discord.TextChannel] = None
    ):
        if await self.data.set(ctx.guild.id, (channel := (channel or ctx.channel)).id): # type: ignore
            if not isinstance(channel, discord.TextChannel):
                raise Cog.reply_error.BadRequest(t(dict(
                    ja="テキストチャンネルでなければいけません。",
                    en="It must be a text channel."
                ), ctx))
            await ctx.reply(t(dict(
                ja="即抜けRTA通知チャンネルを{mention}にしました。",
                en="Immediate Exit RTA Notification Channel to {mention}."
            ), ctx, mention=channel.mention))
        else:
            await ctx.reply(t(dict(
                ja="RTA通知を解除しました。", en="RTA notifications have been unset."
            ), ctx))

    @rta.command(description="Show currently Immediate Quit RTA setting")
    async def show(self, ctx: commands.Context):
        if channel := await self.data.get(ctx.guild.id): # type: ignore
            await ctx.reply(t(dict(
                ja="現在の即抜けRTAのチャンネルは{channel}です。",
                en="The current channel for the instant exit RTA is {channel}."
            ), ctx, channel=self.mention_and_id(channel))) # type: ignore
        else:
            await ctx.reply(t(dict(
                ja="現在何も設定されていません。", en="It is not set yet."
            ), ctx))

    (Cog.HelpCommand(rta)
        .set_description(ja="即抜けRTA通知用のコマンドです", en="Set channel which recording the leaving RTA.")
        .merge_headline(ja="即抜けrta機能を設定します")
        .set_rtevent(ImmediateExitContext, "on_immediate_quit",
            ja="即抜けRTAの通知時に呼ばれるイベントです。",
            en="This event is called at the time of notification of an immediate quit RTA."
        )
        .add_sub(Cog.HelpCommand(setup)
            .set_description(
                ja="即抜けRTAの通知設定を行います。",
                en="Set up a notification for an immediate exit RTA."
            )
            .add_arg(
                "channel", "Channel", "Optional", ja="""対象のチャンネルです。
                入力しなかった場合はコマンドを実行したチャンネルとなります。""",
                en="""Target channel.
                If not entered, it is the channel where the command was executed."""
            )
            .set_extra(
                "Notes", ja="もう一度このコマンドを設定されているチャンネルで実行するとRTA設定をOffにできます。",
                en="Run this command on channel which was set again to turn off the RTA setting."
            ))
        .add_sub(Cog.HelpCommand(show)
            .set_description(
                ja="即抜けRTAの現在の設定を表示します。",
                en="Displays the current settings of the immediate RTA."
            )))

    ON_ERROR = dict(
        ja="即抜けRTA通知メッセージの送信に失敗しました。",
        en="Failed to send Immediate Quit RTA Notification Message"
    )
    SUBJECT = {"ja": "即抜けRTA検知", "en": "Instant Quit RTA detection"}

    @Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        # もし既にRTAメッセージを送信しているまたは参加日が不明の場合はやめる。
        if f"{member.guild.id}-{member.id}" in self.sended or member.joined_at is None:
            return

        joined_after = datetime.now(timezone.utc) - member.joined_at
        if joined_after.days == 0 and joined_after.seconds < 60:
            if (channel := await self.data.get(member.guild.id)) is not None:
                if isinstance(channel, discord.TextChannel):
                    try:
                        await channel.send(
                            embed=Cog.Embed(
                                title=t(IMMEDIATE_EXIT, member.guild),
                                description=t(dict(
                                    ja="{member}が{seconds}秒で抜けてしまいました。",
                                    en="{member} left in {seconds}s."
                                ), member.guild, member=member,
                                seconds=round(joined_after.seconds, 6))
                            )
                        )
                    except discord.Forbidden:
                        self.bot.rtevent.dispatch("on_immediate_quit", ImmediateExitContext(
                            self.bot, member.guild, "ERROR", self.SUBJECT, FORBIDDEN, self.rta
                        ))
                    except Exception as e:
                        self.bot.rtevent.dispatch("on_immediate_quit", ImmediateExitContext(
                            self.bot, member.guild, "ERROR", self.SUBJECT, self.error_to_text(e), self.rta
                        ))
                    else:
                        self.bot.rtevent.dispatch("on_immediate_quit", ImmediateExitContext(
                            self.bot, member.guild, "SUCCESS", self.SUBJECT, "", self.rta
                        ))
                    self.sended[f"{member.guild.id}-{member.id}"] = time()


async def setup(bot):
    await bot.add_cog(RTA(bot))