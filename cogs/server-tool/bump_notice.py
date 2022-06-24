# RT - BumpNotice

from __future__ import annotations

from typing import TypeAlias, Literal

from collections import defaultdict
from asyncio import sleep
from time import time

from discord.ext import commands, tasks
import discord

from core import Cog, RT, DatabaseManager, cursor, t


class DataManager(DatabaseManager):
    "Bump/up通知の設定データを管理します。"

    MODES = ("bump", "up")
    Modes: TypeAlias = Literal["bump", "up"]

    def __init__(self, cog: BumpNotice):
        self.cog = cog

    async def prepare_table(self) -> None:
        "テーブルを準備します。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS BumpNotice(
                GuildId BIGINT NOT NULL, Mode Enum('bump', 'up') NOT NULL,
                PRIMARY KEY (GuildId, Mode)
            );"""
        )

    async def should_notice(self, guild_id: int, mode: Modes, **_) -> bool:
        "通知をセットするべきかどうかを調べます。"
        await cursor.execute(
            "SELECT * FROM BumpNotice WHERE GuildId = %s AND Mode = %s LIMIT 1;",
            (guild_id, mode)
        )
        return bool(await cursor.fetchone())

    async def toggle(self, guild_id: int, mode: Modes, **_) -> bool:
        "設定のオンオフを切り替えます。結果がboolになって返ります。"
        if await self.should_notice(guild_id, mode, cursor=cursor):
            await cursor.execute(
                "DELETE FROM BumpNotice WHERE GuildId = %s AND Mode = %s;",
                (guild_id, mode)
            )
            return False
        await cursor.execute(
            "INSERT INTO BumpNotice VALUES (%s, %s)", (guild_id, mode)
        )
        return True

    async def clean(self) -> None:
        "データを掃除します。"
        async for row in self.fetchstep(cursor, "SELECT * FROM BumpNotice;"):
            if not await self.cog.bot.exists("guild", row[0]):
                await cursor.execute(
                    "DELETE FROM BumpNotice WHERE GuildId = %s AND Mode = %s;",
                    (row[0], row[1])
                )


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
        ), ctx)

    @commands.command(description="Toggle bump notification")
    async def bump(self, ctx):
        await ctx.reply(
            self.get_reply("bump", ctx, (await self.data.toggle(ctx.guild.id, "bump"))
        ))

    Cog.HelpCommand(bump) \
        .merge_description("headline", ja="Bump通知を設定します。")

    @commands.command(description="Toggle up notification")
    async def up(self, ctx):
        await ctx.reply(
            self.get_reply("up", ctx, (await self.data.toggle(ctx.guild.id, "up"))
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
            # もしDissokuなら数秒後に再取得してもう一度この関数on_messageを呼び出す。
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
            self.cache[message.guild.id][data["mode"]] = new = {
                "time": time() + data["time"],
                "channel": message.channel
            }

            # 通知の設定をしたとメッセージを送る。
            try:
                await message.channel.send(
                    embed=Cog.Embed(
                        "通知設定",
                        description=f"{data['mode']}の通知を設定しました。\n"
                                    f"<t:{int(new['time'])}:R>に通知します。",
                    )
                )
            except discord.Forbidden:
                ...


async def setup(bot: RT) -> None:
    await bot.add_cog(BumpNotice(bot))
