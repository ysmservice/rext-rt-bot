# RT - bump notice

from __future__ import annotations

from typing import TypeAlias, Literal

from discord.ext import commands
import discord

from collections import defaultdict
from time import time

from core import Cog, RT, DatabaseManager, cursor, t


class DataManager(DatabaseManager):
    "Bump/up通知の設定データを管理します。"

    TABLES = ("Bump", "Up")
    Modes: TypeAlias = Literal["bump", "up"]

    def __init__(self, cog: BumpNotice):
        self.cog = cog

    async def prepare_table(self) -> None:
        "テーブルを準備します。"
        for table in self.TABLES:
            await cursor.execute(
                f"""CREATE TABLE IF NOT EXISTS {table}Notice(
                    GuildId BIGINT NOT NULL PRIMARY KEY
                );"""
            )

    async def should_notice(self, mode: Modes, guild_id: int, **_) -> bool:
        "通知をセットするべきかどうかを調べます。"
        await cursor.execute(
            f"SELECT * FROM {mode.capitalize()}Notice WHERE GuildId = %s LIMIT 1;",
            (guild_id,)
        )
        return bool(await cursor.fetchone())

    async def toggle(self, mode: Modes, guild_id: int) -> bool:
        "設定のオンオフを切り替えます。結果がboolになって返ります。"
        if await self.should_notice(mode, guild_id, cursor=cursor):
            await cursor.execute(
                f"DELETE FROM {mode.capitalize()}Notice WHERE GuildId = %s;",
                (guild_id,)
            )
            return False
        await cursor.execute(
            f"INSERT INTO {mode.capitalize()}Notice VALUES (%s)",
            (guild_id,)
        )
        return True


class BumpNotice(Cog):
    "Bump/up通知のコグです。"

    IDS = {
        302050872383242240: {
            "mode": "bump",
            "description": ["表示順をアップしたよ", "Bump done", "Bumpeado", "Bump effectue"],
            "time": 7200
        },
        761562078095867916: {
            "mode": "up",
            "description": ["dissoku"],
            "time": 3600
        }
    }
    REPLIES = {"bump": "/bump", "up": "/dissoku up"}
    BUMP_COLOR = 0x00a3af
    UP_COLOR = 0x95859c

    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)
        self.cache = defaultdict(dict)

    async def cog_load(self) -> None:
        await self.data.prepare_table()
        self.notification.start()

    async def cog_unload(self) -> None:
        self.notification.cancel()

    def get_reply(self, mode: DataManager.Modes, ctx: commands.Context, result: bool) -> str:
        "設定完了のメッセージを作成します。"
        return t(dict(
            ja=f"{mode}通知を{'オン' if result else 'オフ'}にしました。",
            en=f"{'Enabled' if result else 'Disabled'} {mode} notification."
        ))

    @commands.command(description="Toggle bump notification")
    async def bump(self, ctx):
        await ctx.reply(
            self.get_reply("bump", ctx, (await self.data.toggle("bump", ctx.guild.id))
        ))

    Cog.HelpCommand(bump) \
        .merge_description("headline", ja="Bump通知を設定します。")

    @commands.command(description="Toggle up notification")
    async def up(self, ctx):
        await ctx.reply(
            self.get_reply("up", ctx, (await self.data.toggle("up", ctx.guild.id))
        ))

    Cog.HelpCommand(up) \
        .merge_description("headline", ja="Up通知を設定します。")

    @tasks.loop(seconds=10)
    async def notification(self):
        for guild in self.cache:
            for mode in self.cache[guild]:
                data = self.cache[guild][mode]
                if time() < data["time"]: continue
                del self.cache[guild][mode]
                await data["channel"].send(
                    embed=Cog.Embed(
                        title=f"Time to {mode}!",
                        description=t(dict(
                            ja=f"{mode}の時間です。\n`{self.REPLIES[mode]}`でこのサーバーの表示順位を上げよう！",
                            en=f"It's time to {mode}.\nDo `{self.REPLIES[mode]}` to up your server!"
                        ), data["channel"].guild)
                    )
                )
            if self.cache[guild] == {}:
                del self.cache[guild]

    async def delay_on_message(self, seconds: int, message: discord.Message) -> None:
        # 遅れて再取得してもう一回on_messageを実行する。
        await sleep(seconds)
        try:
            message = await message.channel.fetch_message(message.id)
        except discord.NotFound:
            ...
        else:
            await self.on_message(message, True)

    @Cog.listener()
    async def on_message(self, message, retry: bool = False):
        if not self.bot.is_ready():
            return

        data = self.IDS.get(message.author.id)
        if not retry and data and data["mode"] != "bump":
            # もしDissoku/rocationsなら数秒後に再取得してもう一度この関数on_messageを呼び出す。
            self.bot.loop.create_task(self.delay_on_message(5, message))
            return
        if not message.guild or not data or not message.embeds:
            return

        desc = message.embeds[0].description
        check = desc and any(
            word in desc for word in data["description"]
        ) if data["mode"] != "up" else (
            message.embeds[0].fields
            and "をアップしたよ" in message.embeds[0].fields[0].name
        )

        if not check:
            return
        row = await self.data.should_notice(message.guild.id, data["mode"])
        if row:
            # 既に書き込まれてるデータに次通知する時間とチャンネルを書き込む。
            self.cache[message.guild.id][data["mode"]] = {
                "time": time() + data[time],
                "channel": message.channel
            }

            # 通知の設定をしたとメッセージを送る。
            try:
                await message.channel.send(
                    embed=Cog.Embed(
                        "通知設定",
                        description=f"{data['mode']}の通知を設定しました。\n"
                                    f"<t:{int(new['notification'])}:R>に通知します。",
                        color=self.bot.colors["normal"]
                    )
                )
            except discord.Forbidden:
                ...


async def setup(bot: RT) -> None:
    await bot.add_cog(BumpNotice(bot))
