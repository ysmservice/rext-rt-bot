# RT - Short URL

from discord.ext import commands
import discord

from aiomysql import Pool

from core import RT, Cog, DatabaseManager, cursor

from .__init__ import FSPARENT


class DataManager(DatabaseManager):
    "セーブデータを管理するためのクラスです。"

    MAX_URL = 150

    def __init__(self, pool: Pool):
        self.pool = pool

    async def prepare_table(self) -> None:
        "テーブルを用意します。"
        await cursor.execute(
            "CREATE TABLE IF NOT EXISTS ShortURL (UserId BIGINT, Url TEXT, Endpoint TEXT);"
        )

    async def read(self, user_id: int, **_) -> list[tuple[str, str]]:
        "データを読み込みます。"
        await cursor.execute(
            "SELECT Url, Endpoint FROM ShortURL WHERE UserId = %s;",
            (user_id,)
        )
        return await cursor.fetchall()

    async def register(self, user_id: int, url: str, endpoint: str) -> None:
        "短縮URLを登録します。"
        assert self.MAX_URL > len(await self.read(user_id, cursor=cursor)), "設定しすぎです。"
        await cursor.execute(
            "SELECT Url FROM ShortURL WHERE Endpoint = %s;", (endpoint,)
        )
        assert not await cursor.fetchone(), "既にそのエンドポイントは使用されています。"
        await cursor.execute(
            "INSERT INTO ShortURL VALUES (%s, %s, %s);",
            (user_id, url, endpoint)
        )

    async def delete(self, user_id: int, endpoint: str) -> None:
        "短縮URLを削除します。"
        await cursor.execute(
            "DELETE FROM ShortURL WHERE UserId = %s AND Endpoint = %s;",
            (user_id, endpoint)
        )


class ShortURL(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self.bot.pool)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.command(
        aliases=("surl", "短縮", "短縮URL"), fsparent=FSPARENT,
        description="Shorten the URL."
    )
    @commands.cooldown(1, 10, commands.BucketType.user)
    @discord.app_commands.describe(
        endpoint=(endpoint_d := "This is the string that comes at the end of the URL."),
        url=(url_d := "URL to shorten.")
    )
    async def short(self, ctx: commands.Context, endpoint: str, *, url: str):
        await ctx.typing()
        await self.data.register(ctx.author.id, url, endpoint)
        await ctx.reply(
            f"Ok: http://rtbo.tk/{endpoint}", allowed_mentions=discord.AllowedMentions.none()
        )

    (Cog.HelpCommand(short)
        .merge_headline(ja="URLを短縮します。")
        .set_description(
            ja="URLを短縮します。",
            en=short.description
        )
        .add_arg("endpoint", "str",
            ja="短縮後のURLの最後にくる文字列です。",
            en=endpoint_d)
        .add_arg("url", "str",
            ja="短縮するURLです。", en=url_d))
    del endpoint_d, url_d


async def setup(bot):
    await bot.add_cog(ShortURL(bot))