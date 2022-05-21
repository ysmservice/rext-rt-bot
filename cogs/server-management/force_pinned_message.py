# RT - Force Pinned Message

from __future__ import annotations

from typing import TypedDict, TypeAlias, Any

from time import time

from discord.ext import commands, tasks
import discord

from orjson import loads, dumps

from core import RT, Cog, t, DatabaseManager, cursor

from rtlib.common.cacher import Cacher
from rtutil.utils import artificially_send
from rtutil.views import TimeoutView

from data import TEST, NO_MORE_SETTING, NUMBER_CANT_USED, FORBIDDEN

from .__init__ import FSPARENT


class ContentJson(TypedDict):
    content: dict[str, Any]
    author: int
Data: TypeAlias = tuple[ContentJson, float, int]


class DataManager(DatabaseManager):

    MAX_PIN = 30

    def __init__(self, cog: ForcePinnedMessage):
        self.cog = cog
        self.caches: dict[int, Data] = {}
        self.pool = self.cog.bot.pool

    async def prepare_table(self) -> None:
        "テーブルを作ります。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS ForcePinnedMessage (
                ChannelId BIGINT NOT NULL PRIMARY KEY, GuildId BIGINT,
                Content JSON, PinInterval FLOAT, BeforeMessage BIGINT
            );"""
        )
        async for row in self.fetchstep(
            cursor, "SELECT ChannelId, Content, PinInterval, BeforeMessage FROM ForcePinnedMessage;"
        ):
            if row[0] not in self.caches:
                self.caches[row[0]] = (loads(row[1]), row[2], row[3])

    def merge(self, channel_id: int, new: dict[int, Any]) -> Data:
        "既存のキャッシュと新しいデータをマージします。"
        return tuple(
            new[index] if index in new else data
            for index, data in enumerate(self.caches[channel_id])
        )

    async def set_interval(self, channel_id: int, interval: float) -> None:
        "インターバルを設定します。"
        assert 0.083 <= interval <= 180, NUMBER_CANT_USED
        await cursor.execute(
            "UPDATE ForcePinnedMessage SET PinInterval = %s WHERE ChannelId = %s;",
            (interval, channel_id)
        )
        if channel_id in self.caches:
            self.caches[channel_id] = self.merge(channel_id, {1: interval})

    async def set_before_message(self, channel_id: int, message_id: int) -> None:
        "前に送信したとされるメッセージのIDを書き込みます。"
        await cursor.execute(
            "UPDATE ForcePinnedMessage SET BeforeMessage = %s WHERE ChannelId = %s;",
            (message_id, channel_id)
        )
        if channel_id in self.caches:
            self.caches[channel_id] = self.merge(channel_id, {2: message_id})

    async def set_(self, channel_id: int, guild_id: int, content: ContentJson) -> None:
        "強制ピン留めを設定します。"
        await cursor.execute(
            "SELECT * FROM ForcePinnedMessage WHERE GuildId = %s;",
            (guild_id,)
        )
        check, length = True, 0
        for row in await cursor.fetchall():
            length += 1
            if row[0] == channel_id:
                check = False
        if check:
            assert length < self.MAX_PIN, NO_MORE_SETTING
        await cursor.execute(
            """INSERT INTO ForcePinnedMessage VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE Content = %s;""",
            (channel_id, guild_id, data := dumps(content).decode(), 1, 0, data)
        )
        current = self.caches.get(channel_id, (None, 1, 0))
        self.caches[channel_id] = (content, current[1], current[2])

    async def delete(self, channel_id: int) -> None:
        "強制ピン留めを削除します。"
        await cursor.execute(
            "DELETE FROM ForcePinnedMessage WHERE ChannelId = %s;",
            (channel_id,)
        )
        if channel_id in self.caches:
            del self.caches[channel_id]

    async def clean(self) -> None:
        await self.clean_data(cursor, "ForcePinnedMessage", "ChannelId")


class ForcePinnedMessageEventContext(Cog.EventContext):
    "強制ピン留めのイベントコンテキストです。"

    channel: discord.TextChannel
    data: Data
FEATURE_NAME = "Force Pin"


class ForcePinnedMessageIntervalModal(discord.ui.Modal):
    "強制ピン留めのインターバルを入力するモーダルです。"

    interval = discord.ui.TextInput(label="Interval")

    def __init__(self, data: DataManager, *args, **kwargs):
        self.data = data
        super().__init__(*args, **kwargs)

    async def on_submit(self, interaction: discord.Interaction):
        assert interaction.channel_id is not None
        try:
            await self.data.set_interval(
                interaction.channel_id, float(str(self.interval))
            )
        except (ValueError, AssertionError):
            await interaction.response.edit_message(
                content=t(NUMBER_CANT_USED, interaction), view=None
            )
        else:
            await interaction.response.edit_message(content="Ok", view=None)


class ForcePinnedMessageSettingView(TimeoutView):
    "強制ピン留めの設定を変えるためのボタンがあるViewです。"

    select: discord.ui.Select

    def __init__(
        self, data: DataManager, message: discord.Message,
        bot_id: int, labels: dict[str, dict[str, str]],
        *args, **kwargs
    ):
        self.data, self.message, self.bot_id = data, message, bot_id
        super().__init__(*args, **kwargs)
        for key, label in labels.items():
            getattr(self, key).label = label

    async def _author_callback(self, interaction: discord.Interaction):
        assert self.message.guild is not None
        # ピン留めするメッセージの情報をまとめる。
        content = {}
        if self.message.content:
            content["content"] = self.message.content
        if self.message.embeds:
            content["embeds"] = [
                embed.to_dict() for embed in self.message.embeds
            ]
        if content:
            # セーブする。
            await self.data.set_(
                self.message.channel.id, self.message.guild.id, ContentJson(
                    content=content, author=self.bot_id
                        if self.select.values[0] == "rt" else interaction.user.id
                )
            )
            await interaction.response.edit_message(content="Ok", view=None)
        else:
            await interaction.response.edit_message(
                content=t(dict(
                    ja="指定されたメッセージが空です。", en="The specified message is empty."
                ), interaction), view=None
            )

    @discord.ui.button(emoji="📌", style=discord.ButtonStyle.green)
    @discord.app_commands.guild_only
    async def set_message(self, interaction: discord.Interaction, _):
        # 送信者を指定するセレクトのViewを作る。
        self.select = select = discord.ui.Select()
        select.add_option(
            label=t(dict(ja="あなた", en="You"), interaction),
            value="user", description=t(dict(
                ja="送信者のアイコンと名前があなたのものになります。",
                en="The sender's icon and name will be yours."
            ), interaction)
        )
        select.add_option(
            label="RT", value="rt", description=t(dict(
                ja="送信者のアイコンと名前がRTになります。",
                en="The sender's icon and name will be RT's."
            ), interaction)
        )
        select.callback = self._author_callback
        # 名前とアイコンをどうするか聞く。
        await interaction.response.edit_message(
            content=t(dict(
                ja="送信者のアイコンと名前はどうしますか？",
                en="What do you want the sender's icon and name to be?"
            ), interaction), view=TimeoutView().add_item(select)
        )

    @discord.ui.button(style=discord.ButtonStyle.blurple, emoji="⏲")
    @discord.app_commands.guild_only
    async def interval(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(ForcePinnedMessageIntervalModal(
            self.data, title=t(dict(
                ja="インターバルを入力してください。", en="Enter the interval."
            ), interaction)
        ))

    @discord.ui.button(style=discord.ButtonStyle.red, emoji="🗑")
    @discord.app_commands.guild_only
    async def delete_message(self, interaction: discord.Interaction, _):
        await self.data.delete(interaction.channel_id) # type: ignore
        await interaction.response.edit_message(content="Ok", view=None)


class ForcePinnedMessage(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)
        self.queues: Cacher[discord.TextChannel, tuple[Data, float]] = \
            self.bot.cachers.acquire(10860.0)
        self.bot.tree.remove_command(FEATURE_NAME)
        self.bot.tree.add_command(discord.app_commands.ContextMenu(
            name=FEATURE_NAME, callback=self.on_pin, type=discord.AppCommandType.message
        ))

    @commands.Cog.listener()
    async def on_help_load(self):
        self.bot.help_.set_help((help_ := Cog.Help())
            .set_category(FSPARENT)
            .set_headline(
                ja="いつも下にくるメッセージを作ります。",
                en="Make the message that comes at the bottom.",
            )
            .set_title("Force Pin")
            .set_description(
                ja="{}\n{}".format(
                    help_.headline["ja"],
                    f"この機能を使うには、コンテキストメニューのアプリの`{FEATURE_NAME}`でメッセージを選択してください。\n"
                    "また、コンテキストメニューをおしたあとに、ピン留め設定以外に、メッセージをどのくらいの周期で下に動かすかを設定するためのボタンもあります。(インターバル)"
                ),
                en="{}\n{}".format(
                    help_.headline["en"],
                    f"To use this feature, select the message in the context menu app `{FEATURE_NAME}`.\n"
                    "After pressing the context menu, there is also a button to set how often the message should move down, in addition to the pinning setting. (interval)"
                )
            )
            .set_extra("Notes",
                ja="""埋め込み作成機能で作った埋め込みをピン留めすることも可能です。
                    (この場合は、RTアイコンモードで埋め込みを作ってください。)""",
                en="""It is also possible to pin embeds created with the Create Embed function.
                    (In this case, please create the embed in RT icon mode.)"""))

    @discord.app_commands.checks.has_permissions(manage_webhooks=True)
    async def on_pin(self, interaction: discord.Interaction, message: discord.Message):
        # ピン留め設定 (コンテキストメニュー)
        if not isinstance(message.author, discord.Member):
            return await interaction.response.defer()
        labels = {
            "set_message": {"ja": "ピン留めを設定する。", "en": "Set pinned message."},
            "delete_message": {"ja": "ピン留めを削除する。", "en": "Delete pinned message."},
            "interval": {"ja": "インターブルを設定する。", "en": "Set interval."}
        }
        for key, value in labels.items():
            labels[key] = t(value, interaction) # type: ignore
        await interaction.response.send_message(
            t(dict(ja="なんの設定をしますか？", en="What do you want to set up?"), interaction),
            view=ForcePinnedMessageSettingView(
                self.data, message, self.bot.user.id, labels # type: ignore
            ), ephemeral=True
        )

    async def cog_load(self):
        await self.data.prepare_table()
        self.pin.start()

    async def cog_unload(self):
        self.pin.cancel()

    SUBJECT = {"ja": "強制ピン留めのメッセージ降ろし", "en": "Forced pinning message drop off"}

    @tasks.loop(seconds=5)
    async def pin(self):
        now = time()
        for channel, (
            (data, interval, before_message), at_that_time
        ) in list(self.queues.items()):
            if now - at_that_time <= interval:
                continue

            ctx = ForcePinnedMessageEventContext(
                self.bot, channel.guild, "ERROR", self.SUBJECT,
                feature=(FSPARENT, FEATURE_NAME),
                channel=channel, data=data
            )
            new = None

            # 送信内容の準備をする。
            kwargs = data["content"].copy()
            # 埋め込みは辞書になっているのでオブジェクトに変える。
            if "embeds" in kwargs:
                kwargs["embeds"] = [
                    discord.Embed.from_dict(embed_raw)
                    for embed_raw in kwargs["embeds"]
                ]

            # 送信を行う。
            try:
                if data["author"] == self.bot.application_id:
                    new = await channel.send(**kwargs)
                else:
                    if member := await self.bot.search_member(
                        channel.guild, data["author"]
                    ):
                        new = await artificially_send(
                            channel, member, wait=True,
                            **kwargs
                        )
            except discord.Forbidden:
                ctx.detail = t(FORBIDDEN, channel.guild)
            else:
                ctx.status = "SUCCESS"
                ctx.detail = ""

            self.bot.rtevent.dispatch("on_force_pinned_message", ctx)
            del self.queues[channel]

            if new is None:
                continue

            # 前に送ったメッセージの削除を試みる。
            if before_message != 0:
                try:
                    before_message = await channel.fetch_message(before_message)
                    if before_message is None:
                        continue
                    await before_message.delete()
                except Exception as e:
                    if TEST:
                        self.bot.ignore(e)

            # 送信したメッセージのIDを次消すために保存しておく。
            await self.data.set_before_message(channel.id, new.id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild and not message.author.bot \
                and isinstance(message.channel, discord.TextChannel) \
                and message.channel.id in self.data.caches:
            self.queues[message.channel] = (self.data.caches[message.channel.id], time())


async def setup(bot):
    await bot.add_cog(ForcePinnedMessage(bot))