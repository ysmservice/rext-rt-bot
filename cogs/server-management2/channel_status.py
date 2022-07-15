# RT - Channel Status

from __future__ import annotations

from collections.abc import AsyncIterator

from discord.ext import commands, tasks
import discord

from core import Cog, RT, DatabaseManager, cursor

from data import NO_MORE_SETTING, SET_ALIASES, DELETE_ALIASES, LIST_ALIASES, FORBIDDEN, CHANNEL_NOTFOUND, NOTFOUND

from .__init__ import FSPARENT


class DataManager(DatabaseManager):
    def __init__(self, cog: ChannelStatus):
        self.cog = cog
        self.pool = self.cog.bot.pool
        self.plan = self.cog.bot.customers.acquire(3, 10)

    async def prepare_table(self) -> None:
        "テーブルを作ります。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS ChannelStatus (
                GuildId BIGINT, ChannelId BIGINT PRIMARY KEY NOT NULL,
                Text TEXT
            );"""
        )

    async def set_(self, guild_id: int, channel_id: int, text: str) -> None:
        "チャンネルステータスを設定します。"
        if len(await self.read(guild_id, cursor=cursor)) >= await self.plan.calculate(guild_id):
            raise Cog.BadRequest(NO_MORE_SETTING)
        await cursor.execute(
            """INSERT INTO ChannelStatus VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE Text = %s;""",
            (guild_id, channel_id, text, text)
        )

    async def read(self, guild_id: int, **_) -> dict[int, str]:
        "チャンネルステータスの設定を取得します。"
        await cursor.execute(
            "SELECT ChannelId, Text FROM ChannelStatus WHERE GuildId = %s;",
            (guild_id,)
        )
        return {row[0]: row[1] for row in await cursor.fetchall()}

    async def read_all(self) -> AsyncIterator[tuple[int, int, str]]:
        "チャンネルステータスの設定を全て取得します。"
        async for data in self.fetchstep(cursor, "SELECT * FROM ChannelStatus;"):
            yield data

    async def delete(self, channel_id: int) -> None:
        "チャンネルステータスの設定を削除します。"
        await cursor.execute(
            "SELECT Text FROM ChannelStatus WHERE ChannelId = %s;",
            (channel_id,)
        )
        if await cursor.fetchone():
            await cursor.execute(
                "DELETE FROM ChannelStatus WHERE ChannelId = %s;",
                (channel_id,)
            )
        else:
            raise Cog.BadRequest(NOTFOUND)

    async def clean(self) -> None:
        "データをお掃除します。"
        await self.clean_data(cursor, "ChannelStatus", "ChannelId")


class UpdateChannelStatusEventContext(Cog.EventContext):
    channel: discord.TextChannel | None


class ChannelStatus(Cog):
    "チャンネルステータスのコグです。"

    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)

    async def cog_load(self):
        await self.data.prepare_table()
        self._update_channels.start()

    async def cog_unload(self):
        self._update_channels.cancel()

    def _update_text(self, text: str, guild: discord.Guild) -> str:
        # 新しい名前を作る。
        if "!tch!" in text:
            # テキストチャンネル数
            text = text.replace("!tch!", str(len(guild.text_channels)))
        if "!vch!" in text:
            # ボイスチャンネル数
            text = text.replace("!vch!", str(len(guild.voice_channels)))
        # ユーザー数
        mb, us, bt = 0, 0, 0
        for member in guild.members:
            us += 1
            if member.bot:
                bt += 1
            else:
                mb += 1
        if "!mb!" in text:
            # メンバー数
            text = text.replace("!mb!", str(mb))
        if "!us!" in text:
            # ユーザー数
            text = text.replace("!us!", str(us))
        if "!bt!" in text:
            # Bot数
            text = text.replace("!bt!", str(bt))
        return text

    @tasks.loop(minutes=5)
    async def _update_channels(self):
        # チャンネルステータスの更新をします。
        guild = None
        async for row in self.data.read_all():
            if guild is None or guild.id != row[0]:
                guild = await self.bot.search_guild(row[0])
            if guild is None:
                continue
            error = None
            channel = guild.get_channel(row[1])
            if channel is None:
                error = CHANNEL_NOTFOUND
            else:
                # チャンネルの名前を新しいのに更新する。
                text = self._update_text(row[2], guild)
                if text == channel.name:
                    continue
                try:
                    await channel.edit(name=text)
                except discord.Forbidden:
                    error = FORBIDDEN
                except discord.HTTPException:
                    error = {"ja": "なんらかのエラーが発生しました。", "en": "Something went wrong."}
            self.bot.rtevent.dispatch("on_update_channel_status", UpdateChannelStatusEventContext(
                self.bot, guild, self.detail_or(error), {
                    "ja": "チャンネルステータス", "en": "Channel Status"
                }, self.text_format(
                    {"ja": "チャンネル: {ch}", "en": "Channel: {ch}"},
                    ch=row[1] if channel is None else self.name_and_id(channel)
                ), self.channel_status
            ))

    @_update_channels.before_loop
    async def _before_update_channels(self):
        await self.bot.wait_until_ready()

    @commands.group(
        aliases=("ch_stats", "csts", "チャンネルステータス", "ちす"), fsparent=FSPARENT,
        description="Displays information about the server on the channel."
    )
    async def channel_status(self, ctx: commands.Context):
        await self.group_index(ctx)

    @channel_status.command(
        "set", aliases=SET_ALIASES,
        description="Set the status of the server to the channel."
    )
    @discord.app_commands.describe(
        text="Text to be displayed in the channel name. More details are in the help section.",
        channel=(_c_d := "Target channel")
    )
    @commands.cooldown(1, 15, commands.BucketType.guild)
    @commands.has_guild_permissions(manage_channels=True)
    async def set_(
        self, ctx: commands.Context, text: str, *,
        channel: discord.abc.GuildChannel | None = None
    ):
        async with ctx.typing():
            assert ctx.guild is not None
            await self.data.set_(ctx.guild.id, (channel or ctx.channel).id, text)
        await ctx.reply("Ok")

    @channel_status.command(aliases=DELETE_ALIASES, description="Delete the setting of the status.")
    @discord.app_commands.describe(channel=_c_d)
    @commands.cooldown(1, 15, commands.BucketType.guild)
    @commands.has_guild_permissions(manage_channels=True)
    async def delete(
        self, ctx: commands.Context, *,
        channel: discord.abc.GuildChannel | None = None
    ):
        async with ctx.typing():
            assert ctx.guild is not None
            await self.data.delete((channel or ctx.channel).id)
        await ctx.reply("Ok")

    @channel_status.command("list", aliases=LIST_ALIASES, description="Displays list of settings.")
    async def list_(self, ctx: commands.Context):
        await ctx.typing()
        assert ctx.guild is not None
        await ctx.reply(embed=self.embed(description="\n".join(
            f"<#{channel_id}>\t{text}"
            for channel_id, text in (await self.data.read(ctx.guild.id)).items()
        )))

    (Cog.HelpCommand(channel_status)
        .merge_description("headline", ja="サーバーのステータスをチャンネル名に設定します。")
        .add_sub(Cog.HelpCommand(set_)
            .merge_description(ja="サーバーステータスをチャンネルに設定します。")
            .add_arg("text", "str",
                ja="""チャンネル名に入れるステータスの文字列です。
                以下に列挙されている二列の文字列の左側にある文字列が、この引数に入れた文字列に含まれる場合に、右側にある文字列に自動で置き換えられます。
                それを利用してチャンネルステータスを作ってください。
                ```
                !tch! テキストチャンネルの数
                !vch! ボイスチャンネルの数
                !mb! Botを含まないサーバーの人数
                !us! Botを含むサーバーの人数
                !bt! Botの数
                ```""",
                en="""This is the status string to be included in the channel name.
                If the string on the left side of the two strings listed below is included in the string you put in this argument, it will be automatically replaced by the string on the right side.
                Use that to create the channel status.
                ```
                !tch! Number of text channels
                !vch! Number of voice channels
                !mb! Number of servers without Bot
                !us! Number of servers with Bot
                !bt! Number of Bot servers
                ```""")
            .add_arg("channel", "Channel", "Optional",
                ja=(_jc_d := """ステータスを設定するチャンネルです。
                指定しない場合はコマンドを実行したチャンネルが使用されます。"""),
                en=(_ec_d := """This is the channel for setting the status.
                If not specified, the channel on which the command was executed is used."""))
            .set_extra("Notes",
                ja="チャンネル名の更新に五分かかることがあります。",
                en="It may take five minutes for the channel name to update."))
        .add_sub(Cog.HelpCommand(delete)
            .merge_description(ja="サーバーステータスの設定を削除します。")
            .add_arg("channel", "Channel", "Optional",
                ja=_jc_d.replace("を設定する", "が設定された"),
                en=_ec_d.replace(" for setting the status.", ".")))
        .add_sub(Cog.HelpCommand(list_)
            .merge_description(ja="サーバーステータスが設定されているチャンネルを列挙します。")))


async def setup(bot: RT) -> None:
    await bot.add_cog(ChannelStatus(bot))