# RT - blocker

from typing import Literal, TypeAlias

from discord.ext import commands
from discord import app_commands
import discord

from rtlib.common.json import loads, dumps

from core import Cog, DataBaseManager, cursor, RT

from .__init__ import FSPARENT


class DataManager(DataBaseManager):

    MODES = ("Emoji", "Stamp", "Reaction")
    MODES_CL: TypeAlias = Literal["Emoji", "Stamp", "Reaction"]
    MODES_L: TypeAlias = Literal["emoji", "stamp", "reaction"]

    def __init__(self, bot: RT):
        self.bot = bot

    async def prepare_table(self) -> None:
        "テーブルを準備します。"
        for table in self.MODES:
            await cursor.execute(
                f"""CREATE TABLE IF NOT EXISTS {table}Blocker(
                    GuildId BIGINT PRIMARY KEY NOT NULL, Blocking BOOLEAN,
                    Roles JSON, Exceptions JSON
                );""")

    async def add_role(self, guild_id: int, mode: MODES_L, role_id: int) -> None:
        "ロールを追加します。"
        mode = mode.capitalize()
        now = self.get_now_roles(guild_id, mode)

        await cursor.execute(
            f"""INSERT INTO {mode}Blocker VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE Roles = %s;""",
            (
                guild_id, False, dumps([role_id]), "[]",
                dumps(now + [role_id])
            )
        )

    async def remove_role(self, guild_id: int, mode: MODES_L, role_id: int) -> None:
        "ロールを削除します。未設定orそのロールが設定されていない場合はValueErrorを送出します。"
        mode = mode.capitalize()
        if not (now := self.get_settings(guild_id, mode)) or guild_id not in now:
            raise ValueError("未設定もしくはロールが設定されていません。")
        now.remove(guild_id)

        await cursor.execute(
            f"""UPDATE {mode}Blocker SET Roles = %s WHERE GuildId = %s;""",
            (dumps(now), guild_id)
        )

    async def get_settings(
        self, guild_id: int, mode: MODES_CL, get_type: str | None = None
    ) -> tuple:
        "設定を取得します。get_typeが指定されていなければ全て返します。"
        await cursor.execute(
            f"SELECT {get_type if get_type else '*'} FROM {mode} WHERE GuildId = %s;",
            (guild_id,)
        )
        return await cursor.fetchone()

    async def get_now_roles(self, guild_id: int, mode: MODES_CL) -> list:
        "現在のロール設定を取得します。この機能が設定されていない場合は[]です。"
        now_roles = self.get_settings(guild_id, mode, "Roles")
        return loads(now_roles[0][0]) if now_roles else []


class Blocker(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(bot)

    async def cog_load(self) -> None:
        await self.data.prepare_table()

    @commands.group(description="Setting blocker.")
    @commands.has_guild_permissions(administrator=True)
    @commands.guild_only()
    async def blocker(self, ctx):
        if ctx.invoked_subcommand: return
        await ctx.send("view blocker settings")

    @blocker.command("toggle", description="Toggles blocker.")
    @app_commands.describe(mode="Blocking type")
    async def _toggle(self, ctx, mode: DataManager.MODES_L):
        await ctx.send("Ok")

    @blocker.group(description="Set blocking roles.")
    async def role(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.send("wrong usage")

    @role.command(description="Add Blocking Roles.")
    async def add(self, ctx, mode: DataManager.MODES_L, role: discord.Role):
        await ctx.send("Ok")


async def setup(bot: RT):
    await bot.add_cog(Blocker(bot))
