# RT - gban

from collections.abc import AsyncIterator

from discord.ext import commands
import discord

from core import Cog, t, DatabaseManager, cursor, RT


class DataManager(DatabaseManager):
    "GBAN関連のデータを管理するマネージャーです。"

    def __init__(self, cog):
        self.cog = cog

    async def prepare_table(self) -> None:
        "テーブルの準備をします。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalBan (
                UserId BIGINT PRYMARY KEY NOT NULL
            );"""
        )
        # GBanのオンオフ切り替え用のデータベースを作成する。
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GBanSetting (
                GuildId BIGINT PRYMARY KEY NOT NULL, Enabled BOOLEAN
            )"""
        )

    async def add_user(self, user_id: int) -> None:
        "ユーザーを追加します。"
        if not await is_exists(user_id, cursor=cursor):
            await cursor.execute("INSERT INTO GlobalBan VALUES (%s);", (user_id,))

    async def is_user_exists(self, user_id: int, **_) -> bool:
        "ユーザーがデータ内に存在するか調べます。"
        await cursor.execute(
            "SELECT * FROM GlobalBan WHERE UserId = %s LIMIT 1;",
            (user_id,)
        )
        return bool(await cursor.fetchone())

    async def get_all_users(self) -> AsyncIterator[tuple[int]]:
        "データベース内に存在する全ユーザーを検索します。"
        async for rows in self.fetchstep(cursor, "SELECT * FROM GlobalBan;"):
            for row in rows:
                yield row
    
    async def toggle_gban(self, guild_id) -> bool:
        "サーバーのGBAN機能のオンオフを切り替えます。"
        await cursor.execute(
            "SELECT Enabled FROM GBanSetting WHERE GuildId = %s LIMIT 1;",
            (guild_id,)
        )
        onoff = False if not (r := await cursor.fetchone()) else not r[0]
        await cursor.execute(
            """INSERT INTO GBanSetting VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE Enabled = %s;""",
            (guild_id, onoff, onoff)
        )


class GBan(Cog):

    def __init__(self, bot):
        self.bot = bot
        self.data = DataManager(self)

    async def cog_load(self) -> None:
        await self.data.prepare_table()

    @commands.command(description="Toggle gban(default true).")
    async def gban(self, ctx):
        await ctx.typing()
        result = True
        await ctx.reply(t(dict(
            ja=f"GBANの設定を{'オン' if result else 'オフ'}にしました。",
            en=f"{'Enabled' if result else 'Disabled'} GBAN setting."
        )))

    @commands.command(description="Check User Gbanned")
    @discord.app_commands.describe(user=(_c_d := "Check user"))
    async def check(self, ctx, user: discord.User):
        await ctx.typing()
        result = True
        await ctx.reply(t(dict(
            ja=f"その人はGBANリストに入っていま{'す' if result else 'せん'}。",
            en=f"The user is {'not ' if not result else ''}found in Gban users."
        )))

    Cog.HelpCommand(gban) \
        .merge_description("headline", ja="GBAN機能のオンオフを変えます(デフォルトはオン)。")
    Cog.HelpCommand(check) \
        .merge_description("headline", ja="ユーザーがGBANされているか確認します。") \
        .add_arg("user", "User", ja="対象のユーザー", en=_c_d)
    
    del _c_d


async def setup(bot: RT):
    await bot.add_cog(GBan(bot))