# RT - gban

from collections.abc import AsyncIterator
from typing import Literal

from discord.ext import commands
import discord

from core import Cog, t, DatabaseManager, cursor, RT

from data import FORBIDDEN


class DataManager(DatabaseManager):
    "GBAN関連のデータを管理するマネージャーです。"

    def __init__(self, cog):
        self.cog = cog

    async def prepare_table(self) -> None:
        "テーブルの準備をします。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalBan (
                UserId BIGINT PRYMARY KEY NOT NULL,
                Reason VARCHAR(2000) NOT NULL
            );"""
        )
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GlobalBanSetting (
                GuildId BIGINT PRYMARY KEY NOT NULL
            );"""
        )

    async def add_user(self, user_id: int, reason: str | None) -> bool:
        "ユーザーを追加します。"
        if not await self.is_user_exists(user_id, cursor=cursor):
            await cursor.execute(
                "INSERT INTO GlobalBan VALUES (%s, %s);",
                (user_id, reason or "RT Global BAN")
            )
            return True
        return False

    async def remove_user(self, user_id: int, _) -> bool:
        "ユーザーを削除します。"
        if await self.is_user_exists(user_id, cursor=cursor):
            await cursor.execute(
                "DELETE FROM GlobalBan WHERE UserId = %s;",
                (user_id,)
            )
            return True
        return False

    async def is_user_exists(self, user_id: int, **_) -> tuple[int, str]:
        "ユーザーがデータ内に存在するか調べます。"
        await cursor.execute(
            "SELECT * FROM GlobalBan WHERE UserId = %s LIMIT 1;",
            (user_id,)
        )
        return await cursor.fetchone()

    async def is_guild_exists(self, guild_id: int, **_) -> bool:
        "サーバーがデータ内に存在するか調べます。"
        await cursor.execute(
            "SELECT * FROM GlobalBanSetting WHERE GuildId = %s LIMIT 1;",
            (guild_id,)
        )
        return bool(await cursor.fetchone())

    async def check(self, user_id: int, guild_id: int) -> Literal[False] | str:
        "ユーザーが指定されたサーバーでBANされるべきかを調べます。もしそうなら理由をw返します。"
        if (await self.is_guild_exists(guild_id, cursor=cursor)
                or not (k := await self.is_user_exists(user_id, cursor=cursor))):
            return False
        return k[1]

    async def get_reason(self, user_id: int) -> str:
        "ユーザーのGBAN理由を取得します。"
        await cursor.execute(
            "SELECT Reason FROM GlobalBan WHERE UserId = %s LIMIT 1;",
            (user_id,)
        )
        return await cursor.fetchone()[0]

    async def get_all_user_ids(self) -> AsyncIterator[int]:
        "データベース内に存在する全ユーザーを検索します。"
        async for row in self.fetchstep(cursor, "SELECT UserId FROM GlobalBan;"):
            yield row[0]

    async def get_all_guild_ids(self) -> AsyncIterator[int]:
        "機能を無効化している全サーバーの設定を抽出します。"
        async for row in self.fetchstep(cursor, "SELECT * FROM GlobalBanSetting;"):
            yield row[0]

    async def toggle_gban(self, guild_id) -> bool:
        "サーバーのGBAN機能のオンオフを切り替えます。"
        await cursor.execute(
            "SELECT * FROM GBanSetting WHERE GuildId = %s LIMIT 1;",
            (guild_id,)
        )
        if await cursor.fetchone():
            await cursor.execute(
                "DELETE FROM GlobalBanSetting WHERE GuildId = %s;",
                (guild_id,)
            )
            return True
        else:
            await cursor.execute(
                "INSERT INTO GlobalBanSetting VALUES (%s);",
                (guild_id,)
            )
            return False

    async def clean(self) -> None:
        "データを掃除します。"
        for table, column in (("GlobalBanSetting", "Guild"), ("GlobalBan", "User")):
            lowered = column.lower()
            async for id_ in getattr(self, f"get_all_{lowered}_ids")():
                if not await self.cog.bot.exists(lowered, id_):
                    await cursor.execute(
                        f"DELETE FROM {table[0]} WHERE {column}Id = %s;",
                        (id_,)
                    )

class GlobalBanEventContext(Cog.EventContext):
    "ユーザーをGBANしたときのイベントコンテキストです。"

    member: discord.Member | discord.User | None
    reason: str | None


class GBan(Cog):
    "GBANのコグです。"

    def __init__(self, bot):
        self.bot = bot
        self.data: DataManager = DataManager(self)

    async def cog_load(self) -> None:
        await self.data.prepare_table()

    @commands.group(description="GlobalBan commands")
    async def gban(self, ctx):
        await self.group_index(ctx)

    @gban.command(description="Toggle gban(default ON).")
    async def toggle(self, ctx):
        async with ctx.typing():
            result = await self.data.toggle_gban(ctx.guild.id)
            await ctx.reply(t(dict(
                ja=f"GBANの設定を{'オン' if result else 'オフ'}にしました。",
                en=f"{'Enabled' if result else 'Disabled'} GBAN setting."
            ), ctx))

    @gban.command(description="Check if user is Gbanned")
    @discord.app_commands.describe(user=(_c_d := "Target user"))
    async def check(self, ctx, *, user: discord.User | discord.Object):
        async with ctx.typing():
            result = await self.data.is_user_exists(user.id)
            await ctx.reply(t(dict(
                ja=f"その人はGBANリストに入っていま{'す。理由:' + result[1] if result else 'せん。'}",
                en=f"The user is {'' if result else 'not '}found in Gban users."
                    f"\nReason: {result[1]}" if result else ''
            ), ctx))

    def call_gban_event(
        self, guild: discord.Guild, error: dict[str, str] | None,
        member: discord.Member | discord.User | None, reason: str | None
    ) -> None:
        "ユーザーをBANしたイベントを呼び出します。"
        self.bot.rtevent.dispatch("on_global_ban_member", GlobalBanEventContext(
            self.bot, guild, self.detail_or(error),
            {"ja": "グローバルBAN", "en": "Global BAN"}, {
                "ja": f"ユーザー:{Cog.name_and_id(member) if member else '不明'}",
                "en": f"User: {Cog.name_and_id(member) if member else 'unknown'}"
            }, self.gban, member=member, reason=reason
        ))

    @Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if (reason := await self.data.check(member.id, member.guild.id)):
            error = None
            try:
                await member.ban(reason=t(dict(
                    ja="RTグローバルBANのため。\n理由: {reason}",
                    en="for RT global BAN.\nReason: {reason}"
                ), member.guild, reason=reason))
            except discord.Forbidden:
                error = FORBIDDEN
            except discord.HTTPException:
                error = {"ja": "なんらかのエラーが発生しました。", "en": "Something went wrong."}
            self.call_gban_event(member.guild, error, member, reason)

    Cog.HelpCommand(gban) \
        .merge_description("headline", ja="GBAN機能です。") \
        .add_sub(Cog.HelpCommand(toggle)
            .merge_description("headline", ja="GBANのオンオフを変えます(デフォルトはオン)。")) \
        .add_sub(Cog.HelpCommand(check)
            .merge_description("headline", ja="ユーザーがGBANされているか確認します。")
            .add_arg("user", "User", ja="対象のユーザー", en=_c_d))
    del _c_d


async def setup(bot: RT) -> None:
    await bot.add_cog(GBan(bot))
