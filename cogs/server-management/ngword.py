# RT - NG Word

from __future__ import annotations

from collections import defaultdict

from discord.ext import commands
import discord

from core import Cog, RT, DatabaseManager, cursor

from data import ADD_ALIASES, REMOVE_ALIASES, LIST_ALIASES, FORBIDDEN


class DataManager(DatabaseManager):
    "セーブデータを管理するためのクラスです。"

    def __init__(self, cog: NgWord):
        self.cog = cog
        self.pool = self.cog.bot.pool
        self.caches: defaultdict[int, list[str]] = defaultdict(list)

    async def setup(self) -> None:
        "DataManagerのセットアップをします。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS NgWord (
                GuildId BIGINT, Word TEXT
            );"""
        )
        async for row in self.fetchstep(cursor, "SELECT * FROM NgWord;"):
            self.caches[row[0]].append(row[1])

    async def read(self, guild_id: int, **_) -> list[str]:
        "データを読み込みます。"
        await cursor.execute(
            "SELECT Word FROM NgWord WHERE GuildId = %s;",
            (guild_id,)
        )
        return [row[0] for row in await cursor.fetchall()]

    async def write(self, guild_id: int, word: str) -> None:
        "データを書き込みます。"
        if word not in await self.read(guild_id, cursor=cursor):
            await cursor.execute(
                "INSERT INTO NgWord VALUES (%s, %s);",
                (guild_id, word)
            )
            self.caches[guild_id].append(word)

    async def delete(self, guild_id: int, word: str) -> None:
        "データを削除します。"
        if guild_id in self.caches and word in self.caches[guild_id]:
            await cursor.execute(
                "DELETE FROM NgWord WHERE GuildId = %s AND Word = %s;",
                (guild_id, word)
            )
            self.caches[guild_id].remove(word)

    async def clean(self) -> None:
        "お掃除をします。"
        await self.clean_data(cursor, "NgWord", "GuildId")


class NgWordEventContext(Cog.EventContext):
    "NGワード削除時のイベントコンテキストです。"

    ngword: str
    message: discord.Message


class NgWord(Cog):
    "NGワードのコグです。"

    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)

    async def cog_load(self):
        await self.data.setup()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or (isinstance(message.author, discord.Member)
                and message.author.guild_permissions.manage_messages):
            return

        for ngword in self.data.caches.get(message.guild.id, ()):
            if ngword in message.content:
                detail = ""
                try:
                    await message.delete()
                except discord.Forbidden:
                    detail = FORBIDDEN
                name = self.name_and_id(message.author)
                self.bot.rtevent.dispatch("on_ngword_delete", NgWordEventContext(
                    self.bot, message.guild, "ERROR" if detail else "SUCCESS",
                    {"ja": "NGワード", "en": "NG Word"}, detail or {
                        "ja": f"発言者：{name}\nNGワード：{ngword}",
                        "en": f"Author: {name}\nNG Word: {ngword}"
                    }, self.ngword
                ))

    @commands.group(
        aliases=("ng", "NGワード", "ngワード", "禁止言葉"),
        description="NG word function."
    )
    @commands.has_guild_permissions(manage_messages=True)
    @commands.cooldown(1, 6, commands.BucketType.guild)
    async def ngword(self, ctx: commands.Context):
        await self.group_index(ctx)

    async def _reply(self, ctx: commands.Context) -> None:
        try:
            await ctx.reply("Ok")
        except discord.HTTPException:
            await ctx.send(f"{ctx.author.mention}, Ok")

    @ngword.command(aliases=ADD_ALIASES, description="Add the ng word.")
    @discord.app_commands.describe(word="The ng word.")
    async def add(self, ctx: commands.Context, *, word: str):
        assert ctx.guild is not None
        await self.data.write(ctx.guild.id, word)
        await self._reply(ctx)

    @ngword.command(aliases=REMOVE_ALIASES, description="Remove the ng word.")
    @discord.app_commands.describe(word="The ng word.")
    async def remove(self, ctx: commands.Context, *, word: str):
        assert ctx.guild is not None
        await self.data.delete(ctx.guild.id, word)
        await self._reply(ctx)

    @ngword.command("list", aliases=LIST_ALIASES, description="Displays the ng words.")
    async def list_(self, ctx: commands.Context):
        assert ctx.guild is not None
        await ctx.reply(embed=self.embed(description=", ".join(map(
            discord.utils.escape_markdown, self.data.caches[ctx.guild.id]
        ))))


async def setup(bot: RT) -> None:
    await bot.add_cog(NgWord(bot))