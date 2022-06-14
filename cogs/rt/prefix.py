# RT - Prefix

from typing import Optional, Literal

from discord.ext import commands
from discord import app_commands

from core import RT, Cog, t, DatabaseManager, cursor


class DataManager(DatabaseManager):
    def __init__(self, bot: RT):
        self.pool, self.bot = bot.pool, bot

    async def prepare_table(self):
        "テーブルを用意します。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GuildPrefix (
                GuildId BIGINT PRIMARY KEY NOT NULL, Prefix TEXT
            );"""
        )
        async for rows in self.fetchstep(cursor, "SELECT * FROM GuildPrefix;"):
            for row in rows:
                self.bot.guild_prefixes[row[0]] = row[1]
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS UserPrefix (
                UserId BIGINT PRIMARY KEY NOT NULL, Prefix TEXT
            );"""
        )
        async for rows in self.fetchstep(cursor, "SELECT * FROM GuildPrefix;"):
            for row in rows:
                self.bot.user_prefixes[row[0]] = row[1]

    async def set(self, mode: Literal["server", "user"], id_: int, prefix: Optional[str] = None):
        "プリフィックスを設定します。"
        if mode == "server":
            if prefix is None:
                if id_ in self.bot.guild_prefixes:
                    await cursor.execute(
                        "DELETE FROM GuildPrefix WHERE GuildId = %s;", (id_,)
                    )
                    del self.bot.guild_prefixes[id_]
            else:
                await cursor.execute(
                    """INSERT INTO GuildPrefix VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE Prefix = %s;""",
                    (id_, prefix, prefix)
                )
                self.bot.guild_prefixes[id_] = prefix
        else:
            # ユーザープリフィックスを設定する。
            if prefix is None:
                if id_ in self.bot.user_prefixes:
                    await cursor.execute(
                        "DELETE FROM UserPrefix WHERE UserId = %s;", (id_,)
                    )
                    del self.bot.user_prefixes[id_]
            else:
                await cursor.execute(
                    """INSERT INTO UserPrefix VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE Prefix = %s;""",
                    (id_, prefix, prefix)
                )
                self.bot.user_prefixes[id_] = prefix

    async def clean(self):
        "お掃除します。"
        for guild_id in self.bot.guild_prefixes:
            if not await self.bot.exists("guild", guild_id):
                await cursor.execute(
                    "DELETE FROM GuildPrefix WHERE GuildId = %s;", (guild_id,)
                )
                del self.bot.guild_prefixes[guild_id]
        for user_id in self.bot.user_prefixes:
            if not await self.bot.exists("user", user_id):
                await cursor.execute(
                    "DELETE FROM UserPrefix WHERE UserId = %s;", (user_id,)
                )
                del self.bot.user_prefixes[user_id]


class Prefix(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(bot)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.command(description="Setting up a custom prefix.")
    @app_commands.describe(mode="Either of user or server", prefix="A Custom prefix")
    async def prefix(
        self, ctx: commands.Context, mode: Literal["user", "server"], *, prefix: Optional[str] = None
    ):
        await ctx.typing()
        await self.data.prepare_table()
        if mode == "guild":
            if not ctx.guild:
                raise commands.NoPrivateMessage()
            if not ctx.author.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])
        await self.data.set_guild(ctx.guild.id, prefix) # type: ignore

        mo_ja = f"{'このサーバー' if mode != "user" else 'あなた'}のカスタムプリフィックスを"
        mo_en = 'of yours' if mode == "user" else 'on this server'
        if prefix is None:
            await ctx.reply(embed=self.embed(
                description=t(dict(
                    ja=f"{mo_ja}未設定にしました。",
                    en=f"Unset custom prefixes {mo_en}."
                ), ctx)
            ))
        else:
            await ctx.reply(embed=self.embed(
                description=t(dict(
                    ja=f"{mo_ja}`{prefix}`に設定しました。",
                    en=f"Custom prefix {mo_en} set to `{prefix}`."
                ), ctx)
            ))

    Cog.HelpCommand(prefix) \
        .set_description(
            ja="""カスタムプリフィックスを設定します。
            カスタムプリフィックスはサーバー毎、またはユーザー毎に設定することができます。
            通常のプリフィックスは`rt!`等ですが、これを設定することで好きなプリフィックスを追加で設定することができます。""",
            en="""Set a custom prefix.  
            Custom prefixes can be set on a per-server basis or a per-user basis.  
            Normal prefixes are `rt!`, etc., but setting this allows you to set additional prefixes of your choice."""
        ) \
        .add_arg("mode", {"en": "`server` or `user`", "ja": "`server`か`user`"},
            ja="サーバーに設定するかユーザーに設定するかです。`server`の場合はそのサーバーで管理者権限が必要です。",
            en="Whether set to server or user. If `server`, you must have administrator permission in the server."
        )
        .add_arg("prefix", "str", "Optional",
            ja="設定するカスタムプリフィックスです。\n未入力の場合は設定解除として扱われます。",
            en="Custom prefix to be set. \nIf not entered, the setting is treated as cancelled."
        ) \
        .merge_headline(ja="カスタムプリフィックスを設定します。")


async def setup(bot: RT):
    await bot.add_cog(Prefix(bot))
