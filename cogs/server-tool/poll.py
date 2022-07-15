# RT - Pool

from __future__ import annotations

from typing import TypeAlias, NamedTuple
from collections.abc import AsyncIterator, Iterable

from itertools import chain
from textwrap import shorten
from time import time

from discord.ext import commands, tasks
import discord

from core import RT, Cog, t, DatabaseManager, cursor

from rtlib.common.json import loads, dumps
from rtlib.common.utils import map_length

from rtutil.utils import artificially_send, set_page, replace_nl
from rtutil.panel import make_panel, extract_emojis
from rtutil.views import EmbedPage

from data import FORBIDDEN, CHANNEL_NOTFOUND, MESSAGE_NOTFOUND


TotalData: TypeAlias = dict[str, list[int]]
RowData = NamedTuple("RowData", (
    ("id_", int), ("guild_id", int), ("channel_id", int), ("message_id", int),
    ("title", str), ("data", TotalData), ("deadline", float), ("created_at", float)
))
MAX_DEADLINE = 2678400
MAX_DEADLINE_DAYS = MAX_DEADLINE / 60 / 60 / 24
MAX_POLLS = 50
class DataManager(DatabaseManager):
    def __init__(self, cog: Poll):
        self.cog = cog
        self.pool = self.cog.bot.pool

    async def prepare_table(self) -> None:
        "テーブルを作ります。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS Poll (
                Id INTEGER AUTO_INCREMENT PRIMARY KEY, GuildId BIGINT,
                ChannelId BIGINT, MessageId BIGINT, Title TEXT,
                TotalData JSON, Deadline DOUBLE, CreatedAt DOUBLE
            );"""
        )

    def _make_data(self, row: tuple) -> RowData:
        # 行のタプルからRowDataを作ります。
        return RowData(*row[:-3], loads(row[-3]), *row[-2:]) # type: ignore

    async def read_whole_data(self, **_) -> AsyncIterator[RowData]:
        "全てのデータを読み込みます。"
        async for row in self.fetchstep(cursor, "SELECT * FROM Poll;"):
            yield self._make_data(row)

    async def read_all(self, guild_id: int, **_) -> list[RowData]:
        "サーバーIDから全ての集計を取得します。"
        await cursor.execute(
            "SELECT * FROM Poll WHERE GuildId = %s;",
            (guild_id,)
        )
        return list(map(self._make_data, await cursor.fetchall()))

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
        if (raw := await self._read(id_, cursor=cursor)) is not None:
            return loads(raw)

    async def stop(self, message: discord.Message, **_) -> TotalData | None:
        "集計データを削除します。"
        id_ = extract_metadata(message.content).id_
        data = await self.read(id_, cursor=cursor)
        await cursor.execute("DELETE FROM Poll WHERE Id = %s;", (id_,))
        return data

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
            raise Cog.reply_error.BadRequest({
                "ja": "既にその投票パネルは集計を終了しています。",
                "en": "That polling panel has already completed its tally."
            })
        await cursor.execute(
            "UPDATE Poll SET TotalData = %s WHERE Id = %s;",
            (dumps(data), id_)
        )

    async def clean(self) -> None:
        "データを掃除をします。"
        await self.clean_data(cursor, "Poll", "ChannelId")


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


def extract_emojis_from_select(select: discord.SelectMenu | discord.ui.Select) -> dict[str, str]:
    "セレクトから絵文字の辞書を取り出します。"
    return {option.value: str(option.emoji) for option in select.options}


def extract_emojis_from_message(message: discord.Message) -> dict[str, str]:
    "メッセージから、メッセージのコンポーネントのセレクトメニューを利用して絵文字を取り出し、辞書にまとめてその辞書を返します。"
    assert isinstance(message.components[0], discord.ActionRow)
    assert isinstance(message.components[0].children[0], discord.SelectMenu)
    return extract_emojis_from_select(message.components[0].children[0])


def make_user_mentions(member_ids: Iterable[int | str]) -> str:
    "渡されたユーザーのIDの全てをメンションにします。"
    return ", ".join(f"<@{member_id}>" for member_id in member_ids)


_YOUR_VOTE = dict(ja="あなたの票", en="Your vote")
class PollView(discord.ui.View):
    def __init__(self, cog: Poll, ctx: commands.Context | None, *args, **kwargs):
        self.cog = cog
        kwargs.setdefault("timeout", None)
        super().__init__(*args, **kwargs)
        # 正しい言語の言葉をItemのlabel等に入れる。
        if ctx is not None:
            self.put.placeholder = t(dict(ja="投票する", en="Put a vote"), ctx.guild)
            self.your_status.label = t(_YOUR_VOTE, ctx.guild)
            self.show_detail.label = t(dict(ja="投票状況", en="Voting status"), ctx.guild)
            self.stop_poll.label = t(dict(ja="投票終了", en="Close voting"), ctx.guild)

    def _extract_metadata(self, interaction: discord.Interaction) -> Metadata:
        # インタラクションからパネルのメタデータを取り出します。
        assert interaction.message is not None
        return extract_metadata(interaction.message.content)

    async def _try_read(self, interaction: discord.Interaction, id_: int) -> TotalData | None:
        # データの読み込みを試みます。
        if (data := await self.cog.data.read(id_)) is None:
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
        metadata = self._extract_metadata(interaction)
        # 現在の集計データを取得する。
        if (data := await self._try_read(interaction, metadata.id_)) is None:
            return
        # 投票したメンバーの票を集計データに反映させる。
        for subject in data.keys():
            is_contain = interaction.user.id in data[subject]
            if subject in select.values:
                if not is_contain:
                    # メンバーの票を追加する。
                    data[subject].append(interaction.user.id)
            elif is_contain:
                # メンバーが投票していない票は消す。(前にした古い票を消す。)
                data[subject].remove(interaction.user.id)
        # 集計データを更新する。
        await self.cog.data.update(metadata.id_, data)

        if metadata.hidden_result:
            await interaction.response.send_message(t(dict(
                ja="投票しました。", en="You were put vote."
            ), interaction), ephemeral=True)
        else:
            # 投票数を見せても良いのなら、投票状況を表示する。
            # 新しい集計結果にメッセージを更新する。
            assert interaction.message is not None
            # 一番票が多いものを調べて、最大の桁を調べる。
            digit = len(str(max(mapped := list(map_length(data)), key=lambda d: d[1])[1]))
            # `map_length`で作ったものを辞書にする。
            mapped = {subject: length for (subject, _), length in mapped}
            # 絵文字を取り出す。
            emojis = extract_emojis_from_message(interaction.message)
            # 埋め込みを更新する。
            embed = interaction.message.embeds[0]
            embed.description = "\n".join(
                f"`{str(mapped[subject]).zfill(digit)}` {emoji} {subject}"
                for subject, emoji in sorted(
                    emojis.items(), key=lambda s: mapped[s[0]], reverse=True
                )
            )
            # 新しい埋め込みにする。
            await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="...", custom_id="poll.your_status", emoji="🗃")
    async def your_status(self, interaction: discord.Interaction, _):
        # ボタンを押した人の投票状況を表示します。
        assert interaction.message is not None
        if (data := await self._try_read_auto_id(interaction)) is not None:
            # 内容を調整して返信する。
            emojis = extract_emojis_from_message(interaction.message)
            await interaction.response.send_message(embed=Cog.Embed(
                title=t(_YOUR_VOTE, interaction), description="\n".join(
                    f"{emojis[subject]} {subject}" for subject in data.keys()
                    if interaction.user.id in data[subject]
                )
            ), ephemeral=True)

    @discord.ui.button(label="...", custom_id="poll.show", emoji="🔍",)
    async def show_detail(self, interaction: discord.Interaction, _):
        # 投票しているユーザーを表示します。
        assert interaction.message is not None
        metadata = extract_metadata(interaction.message.content)

        if metadata.anonymous:
            await interaction.response.send_message(t(dict(
                ja="この投票は匿名投票と設定されているので、投票しているメンバーを見ることはできません。",
                en="This polling panel is set up as an anonymous polling panel, so you will not be able to see which members are voting."
            ), interaction), ephemeral=True)
        elif (data := await self._try_read(interaction, metadata.id_)) is not None:
            if metadata.hidden_result:
                # 投票数見えないモードの場合は投票した人を単純に表示する。
                await interaction.response.send_message(embed=Cog.Embed(
                    t(dict(ja="投票した人", en="Voting Members"), interaction),
                    description=make_user_mentions(chain(*(
                        member_ids for member_ids in data.values()
                    )))
                ), ephemeral=True)
            else:
                # 誰が何に投票したかを見えるようにする。
                emojis = extract_emojis_from_message(interaction.message)
                view = EmbedPage(set_page([
                    Cog.Embed(
                        title=f"{emojis[subject]} {subject} - {length}",
                        description=shorten(make_user_mentions(member_ids), 2000)
                    ) for (subject, member_ids), length in map_length(data)
                ]))
                await interaction.response.send_message(
                    embed=view.embeds[0], view=view, ephemeral=True
                )
                view.set_message(interaction)

    @discord.ui.button(
        label="...", custom_id="poll.stop", emoji="💾",
        style=discord.ButtonStyle.danger
    )
    async def stop_poll(self, interaction: discord.Interaction, _):
        # 集計を停止します。
        assert interaction.message is not None
        if str(interaction.user.id) in interaction.message.content:
            if (data := await self.cog.data.stop(interaction.message)) is not None:
                await self.cog._tally(interaction.message, data, interaction)
        else:
            await interaction.response.send_message(t(dict(
                ja="あなたはこの投票パネルの作者ではないため、集計を終了することはできません。",
                en="You are not the author of this voting panel and therefore cannot close the tally."
            ), interaction), ephemeral=True)


class PollAutoCloseEventContext(Cog.EventContext):
    "投票パネルの自動終了時のイベントコンテキストです。"


class Poll(Cog):
    "投票パネルのコグです。"

    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)

    async def cog_load(self) -> None:
        await self.data.prepare_table()
        self._auto_close_poll.start()

    async def cog_unload(self) -> None:
        self._auto_close_poll.cancel()

    @tasks.loop(minutes=1)
    async def _auto_close_poll(self):
        # 自動で投票パネルを閉じるためのループです。
        guild, now = None, time()
        async with self.data.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                async for data in self.data.read_whole_data(cursor=cursor):
                    if guild is None or guild.id != data.guild_id:
                        guild = self.bot.get_guild(data.guild_id)
                    if guild is None:
                        continue
                    # チャンネルを取得する。
                    error = None
                    if (channel := guild.get_channel(data.channel_id)) is None:
                        error = CHANNEL_NOTFOUND
                    # 投票の期限が切れているか確認する。
                    if error is not None or now < data.deadline:
                        continue
                    # 投票パネルのメッセージの取得を試みる。
                    assert isinstance(channel, discord.Thread | discord.TextChannel)
                    try:
                        message = await channel.fetch_message(data.message_id)
                    except discord.Forbidden:
                        error = FORBIDDEN
                    except discord.NotFound:
                        error = MESSAGE_NOTFOUND
                    else:
                        if message is None:
                            error = MESSAGE_NOTFOUND
                        elif (data := await self.data.stop(
                            message, cursor=cursor
                        )) is not None:
                            # 集計結果に更新する。
                            await self._tally(message, data)

                    self.bot.rtevent.dispatch("on_poll_auto_close", PollAutoCloseEventContext(
                        self.bot, guild, self.detail_or(error), {
                            "ja": "投票パネル", "en": "Polling panel"
                        }, {"ja": "自動集計終了", "en": "Automatic close polling panel"},
                        self.poll, error
                    ))

    @_auto_close_poll.before_loop
    async def _before_auto_close(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_setup(self):
        self.view = PollView(self, None)
        self.bot.add_view(self.view)

    async def _tally(
        self, message: discord.Message, data: TotalData,
        interaction: discord.Interaction | None = None
    ) -> None:
        # 投票パネルを集計結果の埋め込みに編集して更新する。
        emojis = extract_emojis_from_message(message)

        # 投票結果が書いてある投票パネルの埋め込みを作る。
        embed = Cog.Embed(title=t(dict(ja="投票結果", en="Result"), message.guild))
        # 集計結果のグラフを作るためにパーセントを求める。
        counts = {subject: len(data[subject]) for subject in data.keys()}
        max_ = max(counts.items(), key=lambda s: s[1])[1]
        if max_ == 0:
            # 0の場合計算に失敗するので1にする。
            max_ = 1
        # フィールドを追加する。
        for subject, length in counts.items():
            embed.add_field(
                name=f"{emojis[subject]} {subject}",
                value="`{:05.1f}%` {}".format(
                    parsent := length / max_ * 100,
                    discord.utils.escape_markdown("|" * int(parsent / 2) or "...")
                ), inline=False
            )

        # その他の情報を入れる。
        embed.description = message.embeds[0].fields[1].value
        embed.set_footer(text=t(dict(
            ja="これは「{title}」の投票結果で、投票数は{count}です。",
            en='This is the result of voting for "{title}" and the number of votes is {count}.'
        ), message.guild, title=message.embeds[0].title, count=sum(counts.values())))

        if interaction is None:
            assert self.bot.user is not None
            if message.webhook_id is None:
                await message.edit(embed=embed, view=None)
            else:
                assert isinstance(message.channel, discord.TextChannel)
                webhook = discord.utils.get(
                    await message.channel.webhooks(), id=message.webhook_id
                )
                if webhook is not None:
                    await webhook.edit_message(message.id, embed=embed, view=None)
        else:
            await interaction.response.edit_message(embed=embed, view=None)

    @commands.command(
        aliases=("vote", "pl", "vt", "投票", "と"),
        description="Create a polling panel."
    )
    @discord.app_commands.rename(max_="max", min_="min")
    @discord.app_commands.describe(
        max_=(_d_mx := "The maximum number of votes. If set to `-1`, it will be unlimited."),
        min_=(_d_mn := "The minimum number of votes. If set to `-1`, it will be unlimited."),
        anonymous=(_d_a := "It is whether or not you want to go into anonymous mode."),
        deadline=(_d_d := "It is how many days after the closing."),
        hidden_result=(_d_h := "The voting results will not be known until the polls close."),
        title=(_d_t := "The title of polling panel."),
        detail=(_d_dt := "The detail of polling panel."),
        content="Name or ID of role separated by `<nl>`."
    )
    @commands.cooldown(1, 15, commands.BucketType.channel)
    async def poll(
        self, ctx: commands.Context, max_: int = -1, min_: int = -1,
        anonymous: bool = False, deadline: float = MAX_DEADLINE_DAYS,
        hidden_result: bool = False, title: str = "Poll",
        detail: str = "...", *, content: str
    ):
        assert ctx.guild is not None and isinstance(
            ctx.channel, discord.TextChannel | discord.Thread
        ) and isinstance(ctx.author, discord.Member)
        content = replace_nl(content)
        # 絵文字達を取り出す。
        data = extract_emojis(content)
        # 期限を計算する。
        deadline = time() + 60 * 60 * 24 * deadline
        # パネルのViewを作る。
        view = PollView(self, ctx)
        length = 0
        for emoji, subject in data.items():
            length += 1
            view.put.add_option(label=subject, value=subject, emoji=emoji)
        # 最大の投票数の調整を行なう。
        view.put.max_values = length if max_ == -1 else max_
        min_ = 1 if min_ == -1 else min_
        if length < min_:
            min_ = length
        view.put.min_values = min_
        # パネルを送信する。
        message = await artificially_send(
            ctx.channel, ctx.author,
            f"{max_},{min_},{int(anonymous)},{deadline},{int(hidden_result)}",
            embed=discord.Embed(
                title=title, description=make_panel(data),
                color=ctx.author.color
            ).add_field(
                name=t(dict(ja="期限", en="Deadline"), ctx),
                value=f"<t:{int(deadline)}>"
            ).add_field(
                name=t(dict(ja="詳細", en="Detail"), ctx), value=detail
            ), view=view, wait=True
        )
        assert message is not None
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

    (Cog.HelpCommand(poll)
        .merge_description("headline", ja="Create a voting panel.")
        .set_extra("Notes",
            ja="このコマンドは引数が多いのでスラッシュコマンドで実行した方が良いです。",
            en="This command has many arguments, so it is better to execute it with a slash command."
        )
        .add_arg("max", "int", ("default", "-1"),
            ja="投票数の上限です。`-1`にすると無制限となります。", en=_d_mx)
        .add_arg("min", "int", ("default", "-1"),
            ja="投票数の下限です。`-1`にすると無制限になります。", en=_d_mn)
        .add_arg("anonymous", "bool", ("default", "False"),
            ja="匿名モードにするかどうかです。誰が投票しているかわからなくなります。",
            en=f"{_d_a} You will not be able to see who is voting.")
        .add_arg("deadline", "float", ("default", str(MAX_DEADLINE_DAYS)),
            ja="何日後に締め切るかです。", en=_d_d)
        .add_arg("hidden_result", "bool", ("default", "False"),
            ja="投票結果が投票終了までわからないようにします。", en=_d_h)
        .add_arg("title", "str", ("default", "Poll"),
            ja="投票のタイトルです。", en=_d_t)
        .add_arg("detail", "str", ("default", "..."),
            ja="投票の内容です。", en=_d_dt)
        .add_arg("content", "str",
            ja="""投票の選択肢です。以下のように改行して分けます。
            ```
            選択肢1
            選択肢2
            選択肢3
            ```
            スラッシュコマンドの場合は改行を入れることができないので、改行の代わりに`<nl>`または`<改行>`を入れてください。""",
            en="""Voting options. Separate them with a new line as follows.
            ````
            Choice 1
            Option 2
            Option 3
            ```
            Slash commands cannot contain line breaks, so instead of a line break, put `<nl>`."""))
    del _d_mx, _d_mn, _d_a, _d_d, _d_h, _d_t, _d_dt


async def setup(bot: RT) -> None:
    await bot.add_cog(Poll(bot))
