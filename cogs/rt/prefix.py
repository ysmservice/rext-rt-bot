# RT - Prefix

from typing import Optional, Literal, TypeAlias

from discord.ext import commands
from discord import app_commands
import discord

from core import RT, Cog, t, DatabaseManager, cursor


TableType: TypeAlias = Literal["Guild", "User"]
class DataManager(DatabaseManager):
    def __init__(self, bot: RT):
        self.pool, self.bot = bot.pool, bot

    async def prepare_table(self):
        "テーブルを用意します。"
        for table in ("Guild", "User"):
            await cursor.execute(
                f"""CREATE TABLE IF NOT EXISTS {table}Prefix (
                    {table}Id BIGINT PRIMARY KEY NOT NULL, Prefix TEXT
                );"""
            )
            async for rows in self.fetchstep(cursor, f"SELECT * FROM {table}Prefix;"):
                for row in rows:
                    self.bot.prefixes[table][row[0]] = row[1]

    async def set(self, table: TableType, id_: int, prefix: Optional[str] = None):
        "プリフィックスを設定します。"
        if prefix is None:
            if id_ in self.bot.prefixes[table]:
                await cursor.execute(
                    f"DELETE FROM {table}Prefix WHERE GuildId = %s;",
                    (id_,)
                )
                del self.bot.prefixes[table][id_]
        else:
            await cursor.execute(
                f"""INSERT INTO {table}Prefix VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE Prefix = %s;""",
                (id_, prefix, prefix)
            )
            self.bot.prefixes[table][id_] = prefix

    async def clean(self):
        "お掃除します。"
        for table in ("Guild", "User"):
            for id_ in self.bot.prefixes[table]:
                if not await self.bot.exists(table.lower(), id_):
                    await cursor.execute(
                        f"DELETE FROM {table}Prefix WHERE {table}Id = %s;",
                        (id_,)
                    )
                    del self.bot.prefixes[table][id_]


class Prefix(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(bot)

    async def cog_load(self):
        await self.data.prepare_table()

    MO_MSG = {
        "server": {"ja": "このサーバー", "en": 'on this server'},
        "user": {"ja": "あなた", "en": 'of yours'}
    }

    @commands.command(description="Setting up a custom prefix.")
    @app_commands.describe(mode="Either of user or server", prefix="A Custom prefix")
    async def prefix(
        self, ctx: commands.Context, mode: Literal["user", "server"], 
        *, prefix: Optional[str] = None
    ):
        await ctx.typing()
        await self.data.prepare_table()
        if mode == "guild":
            if not ctx.guild or not isinstance(ctx.author, discord.Member):
                raise commands.NoPrivateMessage()
            if not ctx.author.guild_permissions.administrator:
                raise commands.MissingPermissions(["administrator"])

        await self.data.set(
            "User" if mode == "user" else "Guild",
            getattr(ctx, "guild" if mode == "server" else "author").id, prefix
        ) # type: ignore

        if prefix is None:
            await ctx.reply(embed=self.embed(
                description=t(dict(
                    ja=f"{self.MO_MSG[mode]['ja']}のカスタムプリフィックスを未設定にしました。",
                    en=f"Unset custom prefixes {self.MO_MSG[mode]['en']}."
                ), ctx)
            ))
        else:
            await ctx.reply(embed=self.embed(
                description=t(dict(
                    ja=f"{self.MO_MSG[mode]['ja']}のカスタムプリフィックスを`{prefix}`に設定しました。",
                    en=f"Custom prefix {self.MO_MSG[mode]['en']} set to `{prefix}`."
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
        ) \
        .add_arg("prefix", "str", "Optional",
            ja="設定するカスタムプリフィックスです。\n未入力の場合は設定解除として扱われます。",
            en="Custom prefix to be set. \nIf not entered, the setting is treated as cancelled."
        ) \
        .merge_headline(ja="カスタムプリフィックスを設定します。")


async def setup(bot: RT):
    await bot.add_cog(Prefix(bot))
