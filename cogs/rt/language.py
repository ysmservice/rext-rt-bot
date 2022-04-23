# RT - Language

from typing import TypeAlias, Literal, Optional

from discord.ext import commands
from discord import app_commands

from aiomysql import Pool, Cursor

from rtlib.database import DatabaseManager, cursor
from rtlib import RT, Cog, t


Mode: TypeAlias = Literal["User", "Guild"]
class DataManager(DatabaseManager):
    def __init__(self, pool: Pool, bot: RT):
        self.pool, self.bot = pool, bot

    async def prepare_table(self):
        "テーブルを準備します。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS GuildLanguage (
                GuildID BIGINT PRIMARY KEY NOT NULL, Language TINYTEXT
            );"""
        )
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS UserLanguage (
                UserID BIGINT PRIMARY KEY NOT NULL, Language TINYTEXT
            );"""
        )
        await self.update_all_cache()

    async def update_cache(self, mode: Mode, **_):
        "キャッシュを更新します。"
        await cursor.execute("SELECT * FROM {}Language;".format(mode))
        lower_mode = mode.lower()
        for row in await cursor.fetchall():
            getattr(self.bot.language, lower_mode)[row[0]] = row[1]

    async def update_all_cache(self):
        "全てのキャッシュを更新します。"
        await self.update_cache("Guild", cursor=cursor)
        await self.update_cache("User", cursor=cursor)

    async def set(self, mode: Mode, id_: int, language: Optional[str] = None) -> None:
        "設定を行います。"
        if language is None:
            lower_mode = mode.lower()
            if getattr(self.bot.language, lower_mode, None) is not None:
                await cursor.execute(
                    "DELETE FROM {}Language WHERE {}ID = %s;".format(mode, mode),
                    (id_,)
                )
                del getattr(self.bot.language, lower_mode)[id_]
        else:
            await cursor.execute(
                """INSERT INTO {}Language VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE Language = %s;""".format(mode),
                (id_, language, language)
            )
            getattr(self.bot.language, mode.lower())[id_] = language

    @DatabaseManager.ignore
    async def _clean(self, mode: Mode, cursor: Cursor):
        lower_mode = mode.lower()
        for id_, language in getattr(self.bot.language, mode).items():
            if id_:
                if mode == "User":
                    ...

    async def clean(self):
        "ゴミデータを削除します。"
        ...


class Language(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self.bot.pool, self.bot)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.command(
        aliases=("lang", "言語", "言葉"),
        description="Language setting per user/server"
    )
    @commands.cooldown(1, 8, commands.BucketType.user)
    @commands.cooldown(1, 8, commands.BucketType.guild)
    @app_commands.describe(mode="Server setting or user setting", language="The language")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Server", value="Guild"),
        app_commands.Choice(name="Your", value="User")
    ], language=[
        app_commands.Choice(name="日本語", value="ja"),
        app_commands.Choice(name="English", value="en")
    ])
    async def language(
        self, ctx: commands.Context, mode: app_commands.Choice[str],
        *, language: app_commands.Choice[str]
    ):
        if mode.value == "Guild":
            if ctx.guild is None:
                return await ctx.reply(t({
                    "ja": "ここでサーバーの設定をすることはできません。",
                    "en": "You cannot configure the server settings here."
                }, ctx))
            elif not ctx.author.guild_permissions.administrator: # type: ignore
                return await ctx.reply(t({
                    "ja": "この設定をするには管理者権限が必要です。",
                    "en": "Administrative privileges are required to make this setting."
                }, ctx))
        await self.data.set(
            mode.value, ctx.guild.id if mode.value == "Guild" else ctx.author.id, # type: ignore
            language.value
        )
        await ctx.reply(t({
            "ja": "{ja_subject}の言語設定を`{language}`にしました。",
            "en": "Set {en_subject} language setting to {language}."
        }, ctx, language=language.name,
        ja_subject="このサーバー" if mode.value == "Guild" else "あなた",
        en_subject="this server" if mode.value == "Guild" else "このサーバー"))

    Cog.HelpCommand(language) \
        .set_description(
            ja="言語設定をします。", en="Setting language"
        ) \
        .add_arg("mode", "Choice",
            ja="""これはサーバーかあなたかどちらとして設定をするかです。
            `Server`: サーバーでの設定
            `Your`: あなたの設定""",
            en="""This is whether the configuration is done as the server or you.
            `Server`: Configuration on the server
            `Your`: Your settings."""
        ) \
        .add_arg("language", "Choice",
            ja="""どの言語にするかです。
            `日本語`: 日本語として設定します。
            `English`: 英語として設定します。""",
            en="""Which language is to be used.
            Japanese`: Set as Japanese.
            `English`: Set as English."""
        ) \
        .set_examples(
            dict(ja="Your English", en="Your 日本語"),
            dict(ja="あなたの言語を英語に設定します。", en="Set your language as Japanese.")
        ) \
        .update_headline(ja="言語設定を変更します。")


async def setup(bot):
    await bot.add_cog(Language(bot))