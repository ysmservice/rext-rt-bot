# RT - NoIconNotice

from __future__ import annotations

from discord.ext import commands
import discord

from core import Cog, RT, t, DatabaseManager, cursor

from rtlib.common.cacher import Cacher

from data import Colors, FORBIDDEN

from .__init__ import FSPARENT


class DataManager(DatabaseManager):
    def __init__(self, cog: NoIconNotice):
        self.cog = cog
        self.pool = self.cog.bot.pool
        self.caches: Cacher[int, str | None] = self.cog.bot.cachers.acquire(1800.0)

    async def prepare_table(self) -> None:
        "テーブルを作ります。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS NoIconNotice (
                GuildId BIGINT NOT NULL PRIMARY KEY, Text TEXT
            );"""
        )

    async def write(self, guild_id: int, text: str) -> None:
        "設定をします。"
        if text:
            await cursor.execute(
                """INSERT INTO NoIconNotice VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE Text = %s;""",
                (guild_id, text, text)
            )
        else:
            await cursor.execute(
                "DELETE FROM NoIconNotice WHERE GuildId = %s;",
                (guild_id,)
            )
        if guild_id in self.caches:
            if text:
                self.caches[guild_id] = text
            else:
                del self.caches[guild_id]

    async def read(self, guild_id: int) -> str | None:
        "設定を読み込みます。"
        if guild_id not in self.caches:
            await cursor.execute(
                "SELECT Text FROM NoIconNotice WHERE GuildId = %s;",
                (guild_id,)
            )
            self.caches[guild_id] = row[0] if (row := await cursor.fetchone()) else None
        return self.caches[guild_id]

    async def clean(self) -> None:
        "お掃除をします。"
        await self.clean_data(cursor, "NoIconNotice", "GuildId")


class NoIconNoticeEventContext(Cog.EventContext):
    member: discord.Member


class NoIconNotice(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)
        self.sent: Cacher[discord.Member, None] = self.bot.cachers.acquire(180.0)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.command(
        aliases=("nin", "アイコン未設定警告", "あみけ"), fsparent=FSPARENT,
        description="Sends a warning when a person with an unset icon enters the room."
    )
    @discord.app_commands.describe(text="This is the message sent when a person with an unset icon enters the server.")
    @commands.has_guild_permissions(administrator=True)
    async def no_icon_notice(self, ctx: commands.Context, *, text: str = ""):
        async with ctx.typing():
            assert ctx.guild is not None
            await self.data.write(ctx.guild.id, text)
        await ctx.reply("Ok")

    (Cog.HelpCommand(no_icon_notice)
        .merge_headline(ja="アイコン未設定の人が入室した際に警告を送る。")
        .set_description(ja="アイコンが未設定の人が入室した際に警告を送ります。", en=no_icon_notice.description)
        .add_arg("text", "str", "Optional",
            ja="""アイコンが未設定の人が参加した際に警告として送る文です。
                未指定の場合は設定解除とみなします。""",
            en="""This is a statement sent as a warning when a person with an unassigned icon joins.
                If unassigned, it is considered as unset."""))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.bot and member.avatar is None and member not in self.sent \
                and (text := await self.data.read(member.guild.id)) is not None:
            detail = ""
            try:
                await member.send(embed=discord.Embed(
                    title="警告", description=text,
                    color=Colors.warning
                ).set_footer(text=member.guild.name, icon_url=getattr(
                    member.guild.icon, "url", ""
                )))
            except (discord.Forbidden, discord.HTTPException):
                detail = FORBIDDEN
            finally:
                self.sent[member] = None
                self.bot.rtevent.dispatch("on_no_icon_notice", NoIconNoticeEventContext(
                    self.bot, member.guild, "ERROR" if detail else "SUCCESS",
                    {"ja": "NoIconNoticeのアイコン無し警告", "en": "NoIconNotice no icon warning"},
                    detail, self.no_icon_notice
                ))


async def setup(bot: RT) -> None:
    await bot.add_cog(NoIconNotice(bot))