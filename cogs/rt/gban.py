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

    async def add_user(self, user_id: int) -> bool:
        "ユーザーを追加します。"
        if not await self.is_user_exists(user_id, cursor=cursor):
            await cursor.execute("INSERT INTO GlobalBan VALUES (%s);", (user_id,))
            return True
        else:
            return False

    async def remove_user(self, user_id: int) -> bool:
        "ユーザーを削除します。"
        if await self.is_user_exists(user_id, cursor=cursor):
            await cursor.execute(
                "DELETE FROM GlobalBan WHERE UserId = %s;",
                (user_id,)
            )
            return True
        else:
            return False

    async def is_user_exists(self, user_id: int, **_) -> bool:
        "ユーザーがデータ内に存在するか調べます。"
        await cursor.execute(
            "SELECT * FROM GlobalBan WHERE UserId = %s LIMIT 1;",
            (user_id,)
        )
        return bool(await cursor.fetchone())

    async def get_all_users(self) -> AsyncIterator[int]:
        "データベース内に存在する全ユーザーを検索します。"
        async for rows in self.fetchstep(cursor, "SELECT UserId FROM GlobalBan;"):
            for row in rows:
                yield row[0]

    async def get_all_guilds(self) -> AsyncIterator[tuple[int]]:
        "全サーバーの設定を抽出します。"
        async for rows in self.fetchstep(cursor, "SELECT * FROM GBanSetting;"):
            for row in rows:
                yield row

    async def toggle_gban(self, guild_id) -> bool:
        "サーバーのGBAN機能のオンオフを切り替えます。"
        await cursor.execute(
            "SELECT Enabled FROM GBanSetting WHERE GuildId = %s LIMIT 1;",
            (guild_id,)
        )
        onoff = False if not (r := await cursor.fetchone()) else not r[0][0]
        # データがなければ(デフォルトONなら)False、あればその値を反転
        await cursor.execute(
            """INSERT INTO GBanSetting VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE Enabled = %s;""",
            (guild_id, onoff, onoff)
        )

    async def clean(self) -> None:
        "データを掃除します。"
        for table in ("GBanSetting", "GlobalBan"):
            user_or_guild = "User" if table == "GlobalBan" else "Guild"
            lowered = user_or_guild.lower()
            async for id_ in getattr(self, f"get_all_{lowered}")():
                if not await self.bot.exists(lowered, id_):
                    await cursor.execute(
                        f"DELETE FROM {table} WHERE {user_or_guild}Id = %s;",
                        (id_,)
                    )


class GBan(Cog):

    def __init__(self, bot):
        self.bot = bot
        self.data = DataManager(self)

    async def cog_load(self) -> None:
        await self.data.prepare_table()

    @commands.command(description="Toggle gban(default ON).")
    async def gban(self, ctx):
        await ctx.typing()
        result = await self.data.toggle_gban(ctx.guild.id)
        await ctx.reply(t(dict(
            ja=f"GBANの設定を{'オン' if result else 'オフ'}にしました。",
            en=f"{'Enabled' if result else 'Disabled'} GBAN setting."
        )))

    @commands.command(description="Check if user is Gbanned")
    @discord.app_commands.describe(user=(_c_d := "Target user"))
    async def check(self, ctx, user: discord.User | discord.Object):
        await ctx.typing()
        result = self.data.is_user_exists(user.id)
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
