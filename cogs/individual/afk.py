# RT - AFK

from __future__ import annotations

from typing import TypedDict, Literal, Optional
from collections.abc import AsyncIterator

from dataclasses import dataclass
from datetime import datetime

from discord.ext import commands, tasks
import discord

from orjson import loads, dumps

from core.converters import DayOfWeekTimeConverter, TimeConverter, DateTimeFormatNotSatisfiable
from core.utils import set_page, separate_from_iterable, artificially_send
from core.cacher import Cacher
from core.views import EmbedPage
from core import RT, Cog, t, DatabaseManager, cursor

from data import SETTING_NOTFOUND, SET_ALIASES, ADD_ALIASES, REMOVE_ALIASES, SHOW_ALIASES


class Timing(TypedDict):
    "AFKオートメーションのAFK設定をするタイミングのデータの型です。"

    mode: Literal["time", "text"]
    data: str


@dataclass
class Automation:
    "AFKオートメーションのデータを格納するデータクラスです。"

    user_id: int
    id_: str
    timing: Timing
    content: str

    @classmethod
    def from_row(cls, row: tuple) -> Automation:
        "MySQLの行のタプルからクラスのインスタンスを作成します。"
        return cls(row[0], row[1], loads(row[2]), row[3])


class DataManager(DatabaseManager):

    MAX_AUTOMATIONS = 30

    def __init__(self, bot: RT):
        self.bot = bot
        self.pool = self.bot.pool

    async def prepare_table(self):
        "テーブルを用意します。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS afk (
                UserID BIGINT NOT NULL PRIMARY KEY, Content TEXT
            );"""
        )
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS AutoAfk (
                UserID BIGINT, Id TEXT, Timing JSON, Content TEXT
            );"""
        )

    async def get(self, user_id: int, **_) -> str | None:
        "AFKを取得します。"
        await cursor.execute(
            "SELECT Content FROM afk WHERE UserID = %s;", (user_id,)
        )
        if row := await cursor.fetchone():
            return row[0]

    async def set_(self, user_id: int, content: Optional[str] = None) -> None:
        "AFKを設定します。または、解除します。"
        if content is None:
            assert (await self.get(user_id, cursor=cursor)) is not None, {
                "ja": "AFKは最初から何も設定されていません。",
                "en": "AFK is not set to anything from the beginning."
            }
            await cursor.execute(
                "DELETE FROM afk WHERE UserID = %s;",
                (user_id,)
            )
        else:
            await cursor.execute(
                """INSERT INTO afk VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE Content = %s;""",
                (user_id, content, content)
            )

    async def get_automations(self, user_id: int, **_) -> list[Automation]:
        "指定されたユーザーのAFKオートメーションのデータを全て取得します。"
        await cursor.execute(
            "SELECT * FROM AutoAfk WHERE UserID = %s;",
            (user_id,)
        )
        data = []
        for row in await cursor.fetchall():
            data.append(Automation.from_row(row))
        return data

    async def get_automation(self, user_id: int, id_: str) -> None:
        "AFKオートメーションのデータを取得します。"
        await cursor.execute(
            "SELECT Id, Timing, Content FROM AutoAfk WHERE UserID = %s AND Id = %s;",
            (user_id, id_)
        )

    async def get_all_automations(self) -> AsyncIterator[Automation]:
        "全員のAFKオートメーションのデータを取得します。"
        async for row in self.fetchstep(cursor, "SELECT * FROM AutoAfk;"):
            yield Automation.from_row(row)

    async def check_exists(self, user_id: int, id_: str, **_) -> int:
        "既に存在しているかチェックをしてから設定の数を返します。"
        i = 0
        for automation in await self.get_automations(user_id, cursor=cursor):
            assert automation.id_ != id_, {
                "ja": "既に同じ設定名のオートメーションが存在しています。",
                "en": "Automation with the same configuration name already exists."
            }
            i += 1
        return i

    async def add_automation(self, user_id: int, automation: Automation) -> None:
        "AFKオートメーションのデータを書き込みます。"
        assert await self.check_exists(
            user_id, automation.id_, cursor=cursor
        ) < self.MAX_AUTOMATIONS, {
            "ja": "これ以上オートメーションを追加することはできません。",
            "en": "No more automation can be added."
        }
        await cursor.execute(
            "INSERT INTO AutoAfk VALUES (%s, %s, %s, %s);",
            (user_id, automation.id_, dumps(automation.timing).decode(), automation.content)
        )

    async def remove_automation(self, user_id: int, id_: str) -> None:
        "AFKオートメーションのデータを削除します。"
        try:
            assert await self.check_exists(user_id, id_, cursor=cursor) + 1, SETTING_NOTFOUND
        except AssertionError:
            await cursor.execute(
                "DELETE FROM AutoAfk WHERE UserID = %s AND Id = %s;",
                (user_id, id_)
            )

    async def clean(self) -> None:
        "掃除をします。"
        await self.clean_data(cursor, "AutoAfk", "UserID")
        await self.clean_data(cursor, "afk", "UserID")


@dataclass
class Caches:
    "キャッシュを格納するためのクラスです。"

    afk: Cacher[int, str | None]
    automation: Cacher[int, list[Automation]]
    sent: Cacher[tuple[int, int], bool]
    set_: Cacher[int, bool]


class AFK(Cog, DataManager):
    "AFK機能のコグです。"

    def __init__(self, bot: RT):
        self.bot = bot
        self.caches = Caches(
            self.bot.cachers.acquire(360.0),
            self.bot.cachers.acquire(180.0, list),
            self.bot.cachers.acquire(15.0),
            self.bot.cachers.acquire(15.0)
        )
        self.automation_loop.start()
        super(Cog, self).__init__(self.bot) # type: ignore

    SUBJECT = {"ja": "AFKの設定", "en": "Set afk"}

    async def cog_load(self):
        await self.prepare_table()

    @commands.Cog.listener()
    async def on_message_noprefix(self, message: discord.Message):
        if message.guild is None or message.author.bot or not message.content:
            return

        # キャッシュがないなら作る。
        for member in message.mentions + [message.author]:
            if member.id not in self.caches.afk:
                self.caches.afk[member.id] = await self.get(member.id)
        if message.author.id not in self.caches.automation:
            for automation in await self.get_automations(message.author.id):
                self.caches.automation[message.author.id].append(automation)

        # AFKが設定されているユーザーに向けてメンションしているメッセージなら不在通知を行う。
        count = 0
        for member in message.mentions:
            if self.caches.sent.get((message.channel.id, member.id), False):
                # 既に十五秒以内に通知しているのなら通知をしない。
                continue
            if self.caches.afk[member.id] is not None:
                await artificially_send(
                    message.channel, member, # type: ignore
                    self.caches.afk[member.id], additional_name=" - RT AFK",
                    allowed_mentions=discord.AllowedMentions.none()
                )
                self.caches.sent[(message.channel.id, member.id)] = True
                count += 1
            if count == 3:
                break
        # Auto AFK (Text)に当てはまるメッセージの場合はAFKを設定する。
        if not self.caches.set_.get(message.author.id, False):
            for automation in self.caches.automation[message.author.id]:
                if automation.timing["mode"] == "text" \
                        and automation.timing["data"] in message.content:
                    await self.set_(message.author.id, automation.content)
                    self.caches.set_[message.author.id] = True
                    self.caches.afk[message.author.id] = automation.content
                    return
        # AFKが設定されている人ならAFKを解除する。
        if not message.content.startswith(("!", "！")) \
                and self.caches.afk.get(message.author.id):
            self.caches.afk[message.author.id] = None
            await self.set_(message.author.id)
            await message.reply(t(dict(
                ja="AFKを解除しました。", en="AFK has been canceled."
            ), message), delete_after=8)

    @tasks.loop(minutes=1)
    async def automation_loop(self):
        # Timeモードのオートメーションの処理をする。
        now = datetime.now().strftime(DayOfWeekTimeConverter.FORMAT)
        did = []
        async for automation in self.get_all_automations():
            if automation.user_id in did:
                continue
            if automation.timing["mode"] == "time":
                if automation.timing["data"] in now:
                    await self.set_(automation.user_id, automation.content)
                    self.bot.rtevent.dispatch("on_afk_automation", Cog.EventContext(
                        self.bot, automation.user_id, subject=self.SUBJECT, detail={
                            "ja": f"設定名：{automation.id_}",
                            "en": f"SettingName: {automation.id_}"
                        }, feature=self.afk
                    ))
                    did.append(automation.user_id)
        del did

    async def cog_unload(self):
        self.automation_loop.cancel()

    @commands.group(
        aliases=("留守番",), description="Reply absence notification message the AFK",
        fsparent="individual"
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def afk(self, ctx: commands.Context):
        await self.group_index(ctx)

    AFK_HELP = (Cog.HelpCommand(afk)
        .update_headline(ja="メンション時に自動返信をする。")
        .set_description(
            ja="""メンションされた際に特定のメッセージを返信するように設定します。
                その設定は何かしらメッセージを送信すると解除されます。
                RTでは、この機能のことをAFKと呼びます。""",
            en="""Set up the system to reply with a specific message when you are menshoned.
                That setting is removed when some message is sent.
                In RT, this feature is called AFK."""
        )
        .set_extra("Notes",
            ja="メッセージを送信するとAFKが解除されると書きましたが、`.`をメッセージの最初に付けると解除されなくなります。",
            en="I wrote that AFK is canceled when a message is sent, but if you put `.` at the beginning of the message, it will not be canceled."))

    @afk.command(
        "set", aliases=SET_ALIASES,
        description="Set the AFK message."
    )
    @commands.cooldown(1, 15.0, commands.BucketType.user)
    @discord.app_commands.describe(content="Message to be set. If blank, AFK is canceled.")
    async def set_afk(self, ctx: commands.Context, *, content: Optional[str] = None):
        async with ctx.typing():
            await self.set_(ctx.author.id, content)
        await ctx.reply("Ok")

    AFK_HELP.add_sub(Cog.HelpCommand(set_afk)
        .set_description(ja="AFKメッセージを設定します。", en="Set the AFK message.")
        .add_arg("content", "str", "Optional",
            ja="AFKの内容です。もし指定しなかった場合は解除として扱われます。",
            en="The contents of AFK. If not specified, it is treated as a release.")
        .set_examples(dict(
            ja="説教を受けているので返信できません。",
            en="I am unable to reply as I am live streaming."
        ), dict(
            ja="メンションをされた際に「説教を受けているから返信ができない」と返信をするようにします。",
            en="Set to reply \"I can't reply because I'm broadcasting live\" when someone mentions you."
        )))

    @afk.group(
        aliases=("am", "オートメーション", "自動"),
        description="Automatic AFK setting"
    )
    async def automation(self, ctx: commands.Context):
        await self.group_index(ctx)

    AFK_HELP.add_sub(Cog.HelpCommand(automation)
        .set_description(
            ja="""AFK自動化の設定です。
                指定した時間にAFKの設定または指定した文字列が含まれるメッセージ送信時にAFKを自動で設定するようにします。""",
            en="""AFK Automation Settings.
                Enables AFK to be set automatically when AFK is set at a specified time or when a message containing a specified string is sent."""
        ))

    @automation.command(
        aliases=ADD_ALIASES, description="Add an AFK automation setting."
    )
    @commands.cooldown(1, 15, commands.BucketType.user)
    @discord.app_commands.describe(
        name="A name of the setting", mode="The mode of the setting",
        data="A data of the setting", content="The message will be set to afk."
    )
    async def add(
        self, ctx: commands.Context, name: str,
        mode: Literal["time", "text"],
        data: str, *, content: str
    ):
        async with ctx.typing():
            if mode == "time":
                # 最適かどうかを調べる。
                try:
                    await TimeConverter().convert(ctx, data)
                except DateTimeFormatNotSatisfiable:
                    await DayOfWeekTimeConverter().convert(ctx, data)
                await self.add_automation(ctx.author.id, Automation(
                    ctx.author.id, name, Timing(mode=mode, data=data), content
                ))
            else:
                await self.add_automation(ctx.author.id, Automation(
                    ctx.author.id, name, Timing(mode=mode, data=data), content
                ))
        await ctx.reply("Ok")

    AFK_HELP.add_sub(Cog.HelpCommand(add)
        .set_description(
            ja="AFKオートメーションの設定を追加します。", en="Add AFK automation settings."
        )
        .set_extra("Notes",
            ja="最大30個設定することが可能です。",
            en="A maximum of 30 can be set.")
        .add_arg("name", "str",
            ja="設定名です。", en="A name of the setting")
        .add_arg("mode", "Choice",
            ja="""どのタイミングで自動設定を行うかのモードです。
                `time`: 時間
                `text`: 特定の文字列がメッセージに含まれた際""",
            en="""This is the timing at which the automatic configuration will be performed.
                `time`: time
                `text`: When a specific text is included in a message.""")
            # TODO: 時間フォーマットについてまとめたウェブページのリンクを貼る。
        .add_arg("data", "str",
            ja="""`mode`引数のモードに当てはまる適切な値です。
                例えば`mode`を`text`に設定したのなら「寝る」をメッセージに含めた際にAFKが設定されるようになります。""",
            en="""The appropriate value that applies to the mode of the `mode` argument.
                For example, if `mode` is set to `text`, then AFK will be set when "sleep" is included in the message.""")
        .add_arg("content", "str",
            ja="設定するAFKのメッセージです。", en="AFK message to be set.")
        .set_extra("Notes",
            ja="""`text`モードの場合は、一度AFKが設定されたあとに、もう一度AFKを設定する前に20秒待つ必要があります。
                これは連投による過負荷防止のためです。""",
            en="""In `text` mode, once AFK is set, you must wait 20 seconds before setting AFK again.
                This is to prevent overloading due to continuous pitching."""))

    @automation.command(
        aliases=REMOVE_ALIASES,
        description="Remove an AFK automation setting."
    )
    @commands.cooldown(1, 15, commands.BucketType.user)
    @discord.app_commands.describe(name="The name of settin to be deleted.")
    async def remove(self, ctx: commands.Context, *, name: str):
        async with ctx.typing():
            await self.remove_automation(ctx.author.id, name)
        await ctx.reply("Ok")

    AFK_HELP.add_sub(Cog.HelpCommand(remove)
        .set_description(
            ja="AFKオートメーションの設定を削除します。",
            en="Remove an AFK automation setting."
        )
        .add_arg("name", "str", ja="設定名です。", en="A name of the setting."))

    @automation.command(
        "show", aliases=SHOW_ALIASES,
        description="Displays what is currently set for AFK automation."
    )
    async def show_automation(self, ctx: commands.Context):
        async with ctx.typing():
            automations = await self.get_automations(ctx.author.id)
            view = EmbedPage([
                Cog.Embed(
                    "AFK Automation",
                    description=text
                )
                for text in separate_from_iterable((
                    "{}\n{}".format(
                        f"`{automation.id_}` - `{automation.timing['mode']}` - {automation.timing['data']}",
                        f"　　{automation.content}"
                    ) for automation in automations
                ))
            ])
            set_page(view.embeds)
        await view.first_reply(ctx)

    AFK_HELP.add_sub(Cog.HelpCommand(show_automation)
        .set_description(
            ja="設定されているAFKオートメーションを表示します。",
            en="Displays the AFK automation that has been set."
        ))


async def setup(bot):
    await bot.add_cog(AFK(bot))