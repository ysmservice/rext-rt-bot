# RT - Prefix

from typing import Optional

from discord.ext import commands
from discord import app_commands

from core.database import DatabaseManager, cursor
from core import RT, Cog, t


class DataManager(DatabaseManager):
    def __init__(self, bot: RT):
        self.pool, self.bot = bot.pool, bot

    async def prepare_table(self):
        "Prepare a table."
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS Prefix (
                GuildID BIGINT PRIMARY KEY NOT NULL, Prefix TEXT
            );"""
        )
        await cursor.execute("SELECT * FROM Prefix;")
        for row in await cursor.fetchall():
            self.bot.prefixes[row[0]] = row[1]

    async def set(self, guild_id: int, prefix: Optional[str] = None):
        "Set a custom prefix."
        if prefix is None:
            if guild_id in self.bot.prefixes:
                await cursor.execute(
                    "DELETE FROM Prefix WHERE GuildID = %s;", (guild_id,)
                )
                del self.bot.prefixes[guild_id]
        else:
            await cursor.execute(
                """INSERT INTO Prefix VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE Prefix = %s;""",
                (guild_id, prefix, prefix)
            )
            self.bot.prefixes[guild_id] = prefix


class Prefix(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(bot)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.command(description="Setting up a custom prefix.")
    @commands.guild_only()
    @commands.has_guild_permissions(administrator=True)
    @app_commands.describe(prefix="A Custom prefix")
    async def prefix(self, ctx: commands.Context, *, prefix: Optional[str] = None):
        await ctx.trigger_typing()
        await self.data.prepare_table()
        await self.data.set(ctx.guild.id, prefix) # type: ignore
        if prefix is None:
            await ctx.reply(embed=self.embed(
                description=t(dict(
                    ja="このサーバーのカスタムプリフィックスを未設定にしました。",
                    en="Unset custom prefixes on this server."
                ))
            ))
        else:
            await ctx.reply(embed=self.embed(
                description=t(dict(
                    ja="このサーバーのカスタムプリフィックスを{prefix}に設定しました。",
                    en="Custom prefix on here set to `{prefix}`."
                ), ctx, prefix=prefix)
            ))

    Cog.HelpCommand(prefix) \
        .set_description(
            ja="""カスタムプリフィックスを設定します。
            カスタムプリフィックスはサーバー毎に設定することができます。
            通常のプリフィックスは`rt!`等ですが、これを設定することで好きなプリフィックスを追加で設定することができます。""",
            en="""Set a custom prefix.  
            Custom prefixes can be set on a per-server basis.  
            Normal prefixes are `rt!`, etc., but setting this allows you to set additional prefixes of your choice."""
        ) \
        .add_arg("prefix", "str", "Optional",
            ja="設定するカスタムプリフィックスです。\n未入力の場合は設定解除として扱われます。",
            en="Custom prefix to be set. \nIf not entered, the setting is treated as cancelled."
        ) \
        .update_headline(ja="カスタムプリフィックスを設定します。")


async def setup(bot: RT):
    await bot.add_cog(Prefix(bot))