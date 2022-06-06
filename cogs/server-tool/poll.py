# RT - Pool

from __future__ import annotations

from typing import TypeAlias, NamedTuple
from collections.abc import AsyncIterator

from textwrap import shorten
from time import time

from discord.ext import commands
import discord

from core import RT, Cog, t, DatabaseManager, cursor

from rtlib.common.json import loads, dumps
from rtlib.common.utils import map_length

from rtutil.panel import make_panel, tally_panel, extract_emojis
from rtutil.views import TimeoutView, EmbedPage
from rtutil.utils import artificially_send

from data import TOO_SMALL_OR_LARGE_NUMBER


TotalData: TypeAlias = dict[str, list[int]]
RowData = NamedTuple("RowData", (
    ("id_", int), ("guild_id", int), ("channel_id", int), ("message_id", int),
    ("title", str), ("data", TotalData), ("deadline", float), ("created_at", float)
))
MAX_DEADLINE = 2678400
MAX_DEADLINE_DAYS = MAX_DEADLINE / 60 / 60 / 24
MAX_POLLS = 50
class DataManager(DatabaseManager):
    def __init__(self, bot: RT):
        self.bot = bot

    async def prepare_table(self) -> None:
        "テーブルを作ります。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS Poll (
                Id INTEGER AUTO_INCREMENT, GuildId BIGINT,
                ChannelId BIGINT, MessageId BIGINT, Title TEXT,
                TotalData JSON, Deadline DOUBLE, CreatedAt DOUBLE
            );"""
        )

    def _make_data(self, row: tuple) -> RowData:
        # 行のタプルからRowDataを作ります。
        return RowData(*row[:-3], loads(row[-3]), *row[-3:]) # type: ignore

    async def read_whole_data(self) -> AsyncIterator[RowData]:
        "全てのデータを読み込みます。"
        async for row in self.fetchstep(cursor, "SELECT * FROM Poll;"):
            yield self._make_data(row)

    async def read_all(self, guild_id: int, **_) -> set[RowData]:
        "サーバーIDから全ての集計を取得します。"
        await cursor.execute(
            "SELECT * FROM Poll WHERE GuildId = %s;",
            (guild_id,)
        )
        return set(map(self._make_data, await cursor.fetchall()))

    async def _read(self, id_: int, **_) -> str | None:
        # 集計を生で取得します。
        await cursor.execute(
            "SELECT TotalData FROM Poll WHERE Id = %s LIMIT 1;",
            (id_,)
        )
        if row := await cursor.fetchone():
            return row[0]

    async def read(self, id_: int, **_) -> TotalData | None:
        "集計結果を取得します。"
        if (row := await self._read(id_, cursor=cursor)):
            return loads(row[0])

    async def stop(self, id_: int, **_) -> None:
        "集計をストップします。"
        await cursor.execute("DELETE FROM Poll WHERE Id = %s;", (id_,))

    async def start(
        self, guild_id: int, channel_id: int, message_id: int,
        title: str, data: TotalData, deadline: float = MAX_DEADLINE
    ) -> tuple[dict[str, str] | None, int]:
        "集計をスタートします。"
        reply = None
        if len(await self.read_all(guild_id, cursor=cursor)) == MAX_POLLS:
            reply = {
                "ja": f"投票パネルの上限の{MAX_POLLS}に達しました。\nどれかパネルの集計をストップしなければ、次に投票パネルを作った際に一番古いパネルの集計が停止されます。",
                "en": f"The maximum {MAX_POLLS} of the polling panel has been reached.\nIf you do not stop the counting of any of the panels, the next time you create a polling panel, the counting of the oldest panel will be stopped."
            }
        if len(await self.read_all(guild_id, cursor=cursor)) > MAX_POLLS:
            # 上限に達した場合は一番古いパネルの集計を停止する。
            await cursor.execute(
                "DELETE FROM Poll WHERE GuildId = %s ORDER BY CreatedAt ASC LIMIT 1;",
                (guild_id,)
            )
            reply = {
                "ja": "投票パネルの上限に達したため、一番古いパネルの集計を停止しました。",
                "en": "The counting of the oldest panels has been stopped because the maximum number of polling panels has been reached."
            }
        await cursor.execute(
            """INSERT INTO Poll (
                GuildId, ChannelId, MessageId, Title,
                TotalData, Deadline, CreatedAt
            ) VALUES (%s, %s, %s, %s, %s, %s, %s);""",
            (guild_id, channel_id, message_id, title, dumps(data), deadline, time())
        )
        await cursor.execute("SELECT Id FROM Poll WHERE MessageId = %s LIMIT 1;", (message_id,))
        return reply, (await cursor.fetchone())[0]

    async def update(self, id_: int, data: TotalData, **_) -> None:
        "集計を更新します。"
        if (await self._read(id_, cursor=cursor)) is None:
            raise Cog.BadRequest({
                "ja": "既にその投票パネルは集計を終了しています。",
                "en": ""
            })
        await cursor.execute(
            "UPDATE Poll SET TotalData = %s WHERE Id = %s;",
            (id_, dumps(data))
        )


Metadata = NamedTuple("Metadata", (
    ("max_", int), ("min_", int), ("anonymous", bool), ("deadline", float),
    ("hidden_result", bool), ("id_", int), ("author_id", int)
))
def extract_metadata(content: str) -> Metadata:
    "投票パネルのメタデータを取り出します。"
    data = content.split(",")
    return Metadata(
        int(data[0]), int(data[1]), bool(int(data[2])), float(data[3]),
        bool(int(data[4])), int(data[5]), int(data[6])
    )


_YOUR_VOTE = dict(ja="あなたの票", en="Your vote")
class PollView(discord.ui.View):
    def __init__(self, cog: Poll, ctx: commands.Context | None, *args, **kwargs):
        self.cog = cog
        kwargs.setdefault("timeout", None)
        # 正しい言語の言葉をItemのlabel等に入れる。
        if ctx is not None:
            self.put.placeholder = t(dict(ja="投票する", en="Put a vote"), ctx.guild)
            self.your_status.label = t(_YOUR_VOTE, ctx.guild)
        super().__init__(*args, **kwargs)

    def _extract_metadata(self, interaction: discord.Interaction) -> Metadata:
        # インタラクションからパネルのメタデータを取り出します。
        assert interaction.message is not None
        return extract_metadata(interaction.message.content)

    async def _try_read(self, interaction: discord.Interaction, id_: int) -> TotalData | None:
        # データの読み込みを試みます。
        if (data := await self.cog.data.read(id_, cursor=cursor)) is None:
            await interaction.response.send_message(t(dict(
                ja="この投票パネルの集計データが見つかりませんでした。",
                en="I could not find aggregate data for this voting panel."
            ), interaction), ephemeral=True)
        return data

    async def _try_read_auto_id(self, interaction: discord.Interaction) -> TotalData | None:
        # 集計IDを自動で取得して、`._try_read`を実行します。
        if (data := await self._try_read(
            interaction, self._extract_metadata(interaction).id_
        )):
            return data

    @discord.ui.select(placeholder="...", custom_id="poll")
    async def put(self, interaction: discord.Interaction, select: discord.ui.Select):
        # 投票を行うセレクトです。
        # 集計データを更新する。
        async with self.cog.bot.pool.acquire() as conn:
            async with conn.cusror() as cursor:
                id_ = self._extract_metadata(interaction).id_
                if (data := await self._try_read(interaction, id_)) is None:
                    return
                for value in select.values:
                    if interaction.user.id not in data[value]:
                        data[value].append(interaction.user.id)
                await self.cog.data.update(id_, data, cursor=cursor)

        await interaction.response.send_message(t(dict(
            ja="投票しました。", en="You were put the vote."
        ), interaction), ephemeral=True)

    @discord.ui.button(label="...", custom_id="poll.your_status", emoji="🗃")
    async def your_status(self, interaction: discord.Interaction, _):
        # ボタンを押した人の投票状況を表示します。
        assert interaction.message is not None
        emojis = extract_emojis(interaction.message.content)
        if (data := await self._try_read_auto_id(interaction)) is not None:
            # 一番票が多いものを調べて、最大の桁を調べる。
            digit = len(str(max(mapped := map_length(data), key=lambda d: d[1])[1]))
            # `map_length`で作ったものを辞書にする。
            mapped = {subject: length for (subject, _), length in mapped}
            # 内容を調整して返信する。
            await interaction.response.send_message(embed=Cog.Embed(
                title=t(_YOUR_VOTE, interaction), description="\n".join(
                    f"`{str(mapped[value]).zfill(digit)}` {emoji} {value}"
                    for emoji, value in emojis.items()
                    if interaction.user.id in data[value]
                )
            ), ephemeral=True)

    @discord.ui.button(label="...", custom_id="poll.show", emoji="🔍")
    async def show(self, interaction: discord.Interaction, _):
        # 投票状況を表示します。
        assert interaction.message is not None
        metadata = extract_metadata(interaction.message.content)
        if (data := await self._try_read(interaction, metadata.id_)) is not None:
            view = EmbedPage([
                Cog.Embed(title=f"{title} - {length}", description=shorten(
                    ", ".join(f"<@{member_id}>" for member_id in member_ids), 2000
                )) for (title, member_ids), length in sorted(
                    map_length(data), key=lambda d: d[1]
                )
            ])
            await interaction.response.send_message(
                embed=view.embeds[0], view=view, ephemeral=True
            )
            view.set_message(interaction)

    @discord.ui.button(label="...", custom_id="poll.stop", emoji="💾")
    async def stop_poll(self, interaction: discord.Interaction, _):
        ...


class Poll(Cog):
    "投票パネルのコグです。"

    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(bot)

    @commands.Cog.listener()
    async def on_setup(self):
        self.view = PollView(self, None)
        self.bot.add_view(self.view)

    @commands.command(aliases=("vote", "pl", "vt", "投票", "と"))
    @discord.app_commands.rename(max_="max", min_="min")
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def poll(
        self, ctx: commands.Context, max_: int = -1, min_: int = -1,
        anonymous: bool = False, deadline: float = MAX_DEADLINE_DAYS,
        hidden_result: bool = False, title: str = "Poll", *, content: str
    ):
        assert ctx.guild is not None and isinstance(
            ctx.channel, discord.TextChannel | discord.Thread
        ) and isinstance(ctx.author, discord.Member)
        # 絵文字達を取り出す。
        data = extract_emojis(content)
        # 期限を計算する。
        deadline = time() + 60 * 60 * 24 * deadline
        # パネルのViewを作る。
        view = PollView(self, ctx)
        for emoji, subject in data.items():
            view.put.add_option(label=subject, value=subject, emoji=emoji)
        # パネルを送信する。
        message = await artificially_send(
            ctx.channel, ctx.author,
            f"{max_},{min_},{int(anonymous)},{deadline},{int(hidden_result)}",
            embed=discord.Embed(
                title=title, description=make_panel(data), color=ctx.author.color
            ).add_field(
                name=t(dict(ja="期限", en="Deadline"), ctx),
                value=f"<t:{int(deadline)}>"
            ), view=view
        )
        # 投票パネルのデータをセーブする。
        reply, id_ = await self.data.start(ctx.guild.id, ctx.channel.id, message.id, title, {
            value: [] for value in data.values()
        }, deadline)
        # 集計IDを追記する。
        await message.edit(content=f"{message.content},{id_},{ctx.author.id}")
        # 必要であれば返信を行う。
        if reply is None:
            if ctx.interaction is not None:
                await ctx.interaction.response.send_message("Ok", ephemeral=True)
        else:
            await ctx.reply(t(reply, ctx))


async def setup(bot: RT) -> None:
    await bot.add_cog(Poll(bot))