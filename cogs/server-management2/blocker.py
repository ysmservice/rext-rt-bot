# RT - blocker

from typing import Literal, TypeAlias

from discord.ext import commands
from discord import app_commands
import discord

from collections import defaultdict

from rtlib.common.json import loads, dumps
from core import Cog, DataBaseManager, cursor, RT

from .__init__ import FSPARENT


class DataManager(DataBaseManager):

    MODES_CL: TypeAlias = Literal["Emoji", "Stamp", "Reaction"]
    MODES_L: TypeAlias = Literal["emoji", "stamp", "reaction", "all"]
    MODES = ("emoji", "stamp", "reaction")

    def __init__(self, bot: RT):
        self.bot = bot
        # 設定のonoffだけキャッシュに入れておく。
        self.onoff_cache = defaultdict(dict)

    async def prepare_table(self) -> None:
        "テーブルを準備します。"
        for table in ("Emoji", "Stamp", "Reaction"):
            await cursor.execute(
                f"""CREATE TABLE IF NOT EXISTS {table}Blocker(
                    GuildId BIGINT PRIMARY KEY NOT NULL, Blocking BOOLEAN,
                    Roles JSON, Exceptions JSON
                );""")
            async for rows in self.fetchstep(cursor, f"SELECT GuildId, Blocking FROM {table}Blocker;"):
                for row in rows:
                    self.onoff_cache[row[0]][table] = row[1]

    async def toggle(self, guild_id: int, table: MODES_L) -> bool | tuple[bool]:
        "設定のオンオフを切り替えます。"
        if table == "all":
            return (await self.toggle(guild_id, mo) for mo in self.MODES)

        table = table.capitalize()

        if guild_id not in self.onoff_cache:
            await cursor.execute(
                f"INSERT INTO {table}Blocker VALUES (%s, true, %s, %s)",
                (guild_id, "[]", "{}")
            )
            self.onoff_cache[guild_id][table] = True
            return True

        onoff = not self.onoff_cache[guild_id][table]
        await cursor.execute(
            f"UPDATE {table}Blocker Blocking = %s WHERE GuildId = %s",
            (onoff, guild_id)
        )
        self.onoff_cache[guild_id][table] = onoff
        return onoff

    async def add_role(self, guild_id: int, table: MODES_L, role_id: int) -> None:
        "ロールを追加します。"
        if table == "all":
            for mo in ("emoji", "stamp", "reaction"):
                await self.add_role(guild_id, mo, role_id)
            return

        table = table.capitalize()

        if role_id in (now := self.get_now_roles(guild_id, table)):
            raise ValueError("既に登録しています。")

        await cursor.execute(
            f"""INSERT INTO {table}Blocker VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE Roles = %s;""",
            (guild_id, False, dumps([role_id]), "[]",
                dumps(now + [role_id]))
        )

    async def remove_role(
        self, guild_id: int, table: MODES_L, role_id: int
    ) -> list[MODES_L] | None:
        """ロールを削除します。未設定orそのロールが設定されていない場合はValueErrorを送出します。
        table引数が`all`だった場合には削除に成功したテーブルのリストを返します。"""
        if table == "all":
            succeed = []
            for mo in ("emoji", "stamp", "reaction"):
                try: await self.remove_role(guild_id, mo, role_id)
                except ValueError: pass
                else: succeed.append(mo)
            return succeed

        table = table.capitalize()

        if not (now := self.get_now_roles(guild_id, table)) or guild_id not in now:
            raise ValueError("未設定もしくはロールが設定されていません。")

        now.remove(guild_id)
        await cursor.execute(
            f"""UPDATE {table}Blocker SET Roles = %s WHERE GuildId = %s;""",
            (dumps(now), guild_id)
        )

    async def get_settings(
        self, guild_id: int, mode: MODES_CL, get_type: str | None = None
    ) -> tuple:
        "設定を取得します。get_typeが指定されていなければ全て返します。"
        await cursor.execute(
            f"""SELECT {get_type if get_type else '*'} FROM {mode}Blocker
                WHERE GuildId = %s LIMIT 1;""",
            (guild_id,)
        )
        return await cursor.fetchone()

    async def get_now_roles(self, guild_id: int, mode: MODES_CL) -> list:
        "現在のロール設定を取得します。この機能が設定されていない場合は[]です。"
        now_roles = self.get_settings(guild_id, mode, "Roles")
        return loads(now_roles[0][0]) if now_roles else []


class BlockerDeleteEventContect(Cog.EventContext):
    "ブロッカー機能で何かを削除したときのベースイベントコンテキストです。"
    channel: discord.TextChannel | None
    message: discord.Message | None
    member: discord.Member | None

class BlockerDeleteEmojiEventContect(BlockerDeleteEventContect):
    "ブロッカー機能で絵文字を削除したときのイベントコンテキストです。"
    emoji: discord.Emoji | None

class BlockerDeleteStampEventContect(BlockerDeleteEventContect):
    "ブロッカー機能でスタンプを削除したときのイベントコンテキストです。"
    stamp: discord.Sticker | discord.StickerItem | None


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

    @blocker.command(description="Toggles blocker.")
    @app_commands.describe(mode="Blocking type")
    async def toggle(self, ctx, mode: DataManager.MODES_L):
        await ctx.send("Ok")

    @blocker.group(description="Set blocking roles.")
    async def role(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.send("wrong usage")

    @role.command(description="Add Blocking Roles.")
    @app_commands.describe(mode="Blocking type", role="Adding role")
    async def add(self, ctx, mode: DataManager.MODES_L, role: discord.Role):
        await ctx.send("Ok")

    @commands.Cog.listener()
    async def on_message(self, message):
        if not ctx.guild or message.author.bot or \
                message.guild.id not in self.data.onoff_cache:
            return
        pass


async def setup(bot: RT):
    await bot.add_cog(Blocker(bot))
