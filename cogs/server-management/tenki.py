# RT - Tenki

from __future__ import annotations

from typing import NamedTuple, Literal, Any
from collections.abc import AsyncIterator

from datetime import datetime

from discord.ext import commands, tasks
import discord

from aiohttp import ClientSession

from core.utils import make_default
from core import RT, Cog, t, DatabaseManager, cursor

from rtlib.common.cacher import Cacher
from rtutil.views import TimeoutView, EmbedPage
from rtutil.utils import make_datetime_text
from rtutil.converters import TimeConverter, DateTimeFormatNotSatisfiable
from rtutil.collectors import CITY_CODES, tenki

from data import SHOW_ALIASES, SET_ALIASES

from .__init__ import FSPARENT


Data = NamedTuple("Data", (
    ("id_", int), ("mode", Literal["user", "channel"]),
    ("pref", str), ("city", str), ("time", str)
))
class DataManager(DatabaseManager):
    def __init__(self, cog: Tenki):
        self.cog = cog
        self.pool = self.cog.bot.pool

    async def prepare_table(self):
        "テーブルを作ります。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS Tenki (
                Id BIGINT PRIMARY KEY NOT NULL,
                Mode ENUM('user', 'channel'),
                Pref TEXT, City TEXT, NoticeTime TEXT
            );"""
        )

    async def write(
        self, id_: int, mode: Literal["user", "channel"],
        pref: str, city: str, time: str
    ) -> None:
        "データを書き込みます。"
        await cursor.execute(
            """INSERT INTO Tenki VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE Pref = %s, City = %s, NoticeTime = %s;""",
            (id_, mode, pref, city, time, pref, city, time)
        )

    async def delete(self, id_: int, **_) -> None:
        "データを消します。"
        await cursor.execute("DELETE FROM Tenki WHERE Id = %s", (id_,))

    async def read(self, id_: int) -> Data | None:
        "データを読み込みます。"
        await cursor.execute("SELECT * FROM Tenki WHERE Id = %s;", (id_,))
        if row := await cursor.fetchone():
            return Data(*row)

    async def read_all(self, **_) -> AsyncIterator[Data]:
        "全てのデータを読み込みます。"
        async for row in self.fetchstep(cursor, "SELECT * FROM Tenki;"):
            yield Data(*row)

    async def clean(self) -> None:
        async for row in self.fetchstep(cursor, "SELECT * FROM Tenki;"):
            if (row[1] == "user" and not await self.cog.bot.exists("user", row[0])) \
                    or (row[1] == "channel" and not await self.cog.bot.exists("channel", row[0])):
                await self.delete(row[0], cursor=cursor)


class CitySelectView(TimeoutView):
    """市町村を選択します。
    `set`モードでは通知設定を行うので、追加で送信先と何時に送るかのセレクトも選択後に返信します。"""

    def __init__(
        self, data: DataManager, mode: Literal["show", "set"],
        pref: str, *args, **kwargs
    ):
        self.data, self.mode, self.pref = data, mode, pref
        super().__init__(*args, **kwargs)
        for city, id_ in CITY_CODES[pref].items():
            self.select_city.add_option(label=city, value=id_, description=id_)

    @discord.ui.select()
    async def select_city(self, interaction: discord.Interaction, select: discord.ui.Select):
        if self.mode == "set":
            # await self.data.write(interaction.user.id, "user")
            self.which_select = discord.ui.Select()
            self.which_select.add_option(
                label="このチャンネル", value=f"c{interaction.channel_id}",
                description="このチャンネルに通知が送られます。"
            )
            self.which_select.add_option(
                label="あなたのDM", value=f"u{interaction.user.id}",
                description="あなたのDMに通知が送られます。"
            )
            self.which_select.callback = self.select_which
            view = TimeoutView()
            view.add_item(self.which_select)
            await interaction.response.edit_message(content="どこに通知を送信しますか？", view=view)
        else:
            view = await self.data.cog.make_content(select.values[0])
            await interaction.response.edit_message(
                content=None, embed=view.embeds[0], view=view
            )
        view.set_message(interaction)

    async def select_which(self, interaction: discord.Interaction):
        # どこに通知を送信するかが指定されたら。
        self.when_select = discord.ui.Select()
        for i in range(24):
            self.when_select.add_option(
                label=(value := f"{str(i).zfill(2)}:00"), value=value
            )
        self.when_select.callback = self.select_when
        view = TimeoutView()
        view.add_item(self.when_select)
        await interaction.response.edit_message(content="いつ通知を送信しますか？", view=view)
        view.set_message(interaction)

    async def select_when(self, interaction: discord.Interaction):
        # いつ通知を送信するか指定されたら設定を行う。
        await self.data.write(
            int(self.which_select.values[0][1:]),
            "user" if self.which_select.values[0][0] == "u" else "channel",
            self.pref, self.select_city.values[0], self.when_select.values[0]
        )
        await interaction.response.edit_message(content="Ok", view=None)


class PrefSelect(discord.ui.Select):
    "都道府県選択のViewで使うSelectです。"

    view: PrefSelectView

    async def callback(self, interaction: discord.Interaction):
        view = CitySelectView(
            self.view.data, self.view.mode, self.values[0] # type: ignore
        )
        await interaction.response.edit_message(content="地域を選択してください。", view=view)
        view.set_message(interaction)


class PrefSelectView(TimeoutView):
    "都道府県選択のViewです。"

    def __init__(self, data: DataManager, mode: Literal["show", "set"], *args, **kwargs):
        self.data, self.mode = data, mode
        super().__init__(*args, **kwargs)
        i, select = 0, None
        for pref in CITY_CODES.keys():
            if select is None:
                select = PrefSelect()
            i += 1
            select.add_option(label=pref, value=pref)
            if i == 25:
                self.add_item(select)
                i, select = 0, None
        if select is not None:
            self.add_item(select)


class TenkiNotificationEventContext(Cog.EventContext):
    target: discord.TextChannel | discord.User
    data: dict[str, Any]


YET = "(まだ不明)"


class Tenki(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)
        self.caches: Cacher[str, dict[str, Any]] = self.bot.cachers.acquire(3600.0)

    async def make_content(self, city: str) -> EmbedPage:
        "天気予報を取得して埋め込みを作りそれのEmbedPageを作ります。"
        if city not in self.caches:
            self.caches[city] = await tenki(self.session, city)
        data = self.caches[city]
        view = EmbedPage([
            Cog.Embed(title="{}の{}の{}の天気".format(
                forecast['dateLabel'], data["location"]["prefecture"],
                data["location"]["city"]
            ))
                .add_field(name="天気", value=forecast["detail"]["weather"] or YET)
                .add_field(name="風", value=forecast["detail"]["wind"] or YET)
                .add_field(name="波", value=forecast["detail"].get("wave") or YET)
                .add_field(name="気温", value="最低気温：{}度\n最大気温：{}度".format(
                    forecast["temperature"]["min"]["celsius"] or YET,
                    forecast["temperature"]["max"]["celsius"] or YET
                ))
                .add_field(name="降水確率", value="\n".join(
                    "{}~{}時：{}".format(content[0][1:], content[1], value)
                    for key, value in forecast["chanceOfRain"].items()
                    if (content := key.split("_")) or True
                ))
                .set_footer(
                    text=data["copyright"]["title"],
                    icon_url=data["copyright"]["image"]["url"]
                )
            for forecast in data["forecasts"]
        ])
        view.embeds[0].description = data["description"]["text"]
        return view

    async def cog_load(self):
        self.session = ClientSession()
        await self.data.prepare_table()
        self.notification.start()

    async def cog_unload(self):
        self.notification.cancel()
        await self.session.close()

    SUBJECT = make_default("天気予報通知")

    @tasks.loop(minutes=1)
    async def notification(self):
        "天気予報通知を行います。"
        now = make_datetime_text(datetime.now())
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                async for data in self.data.read_all(cursor=cursor):
                    if data.time != now:
                        continue
                    if data.mode == "user":
                        sendable = self.bot.get_user(data.id_)
                    else:
                        sendable = self.bot.get_channel(data.id_)
                        assert isinstance(sendable, discord.TextChannel)
                    if sendable is None:
                        continue
                    ctx = TenkiNotificationEventContext(
                        self.bot, sendable if isinstance(sendable, discord.User)
                            else sendable.guild, "SUCCESS", self.SUBJECT
                    )
                    try:
                        await sendable.send(embed=(await self.make_content(data.city)).embeds[0])
                    except discord.Forbidden:
                        ctx.detail = t(Cog.FORBIDDEN, sendable)
                        ctx.status = "ERROR"
                    self.bot.rtevent.dispatch("on_tenki_notification", ctx)

    @notification.before_loop
    async def before_notification(self):
        await self.bot.wait_until_ready()

    @commands.group(
        aliases=("天気",),
        description="日本の天気予報を表示したりするコマンドです。"
    )
    async def tenki(self, ctx: commands.Context):
        await self.group_index(ctx)

    @tenki.command(aliases=SHOW_ALIASES, description="天気予報を表示します。")
    async def show(self, ctx: commands.Context):
        view = PrefSelectView(self.data, "show")
        view.set_message(ctx, await ctx.reply("都道府県を選択してください。", view=view))

    @tenki.command("set", aliases=SET_ALIASES, description="天気予報通知を設定します。")
    @discord.app_commands.rename(set_="set")
    @discord.app_commands.describe(
        set_=(s_d := "設定を書き込むか削除するかです。"),
        mode=(m_d := "`set`引数を`False`にした場合で、どの設定を削除するかです。")
    )
    async def set_(
        self, ctx: commands.Context, set_: bool = True,
        mode: Literal["user", "channel", "none"] = "none"
    ):
        if set_:
            view = PrefSelectView(self.data, "set")
            view.set_message(ctx, await ctx.reply("都道府県を選択してください。", view=view))
        elif mode == "none":
            await ctx.reply("第三引数は`channel`か`user`でなければいけません。")
        else:
            async with ctx.typing():
                await self.data.delete(ctx.author.id if mode == "user" else ctx.channel.id)
            await ctx.reply("Ok")

    (Cog.HelpCommand(tenki)
        .merge_headline(ja=tenki.description, en=tenki.description)
        .set_description(ja=tenki.description, en=tenki.description)
        .add_sub(Cog.HelpCommand(show)
            .set_description(ja=show.description, en=show.description))
        .add_sub(Cog.HelpCommand(set_)
            .set_description(ja=set_.description)
            .add_arg("set_", "bool", ("default", "True"), ja=s_d)
            .add_arg("mode", "Choice", ("default", "none"),
                ja=f"""{m_d}
                    `user` ユーザーへの通知設定
                    `channel` (コマンドを実行した)チャンネルへの通知設定
                    `none` デフォルト値, これは削除対象として設定できません。""")))
    del s_d, m_d


async def setup(bot):
    await bot.add_cog(Tenki(bot))