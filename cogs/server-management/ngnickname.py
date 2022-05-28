# RT - Ng Nick Name

from __future__ import annotations

from discord.ext import commands
import discord

from core import Cog, t, RT, DatabaseManager, cursor

from data import (
    FORBIDDEN, NO_MORE_SETTING, ALREADY_NO_SETTING,
    ADD_ALIASES, REMOVE_ALIASES, LIST_ALIASES
)

from .__init__ import FSPARENT


class DataManager(DatabaseManager):
    "NGニックネームの設定の管理をするためのクラスです。"

    def __init__(self, cog: NgNickName):
        self.cog = cog
        self.pool = self.cog.bot.pool

    async def prepare_table(self) -> None:
        "テーブルを作ります。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS NgNickName (
                GuildId BIGINT, Word TEXT
            );"""
        )

    async def get(self, guild_id: int, **_) -> list[str]:
        "ニックネームのNGワードのリストを取得します。"
        await cursor.execute(
            "SELECT Word FROM NgNickName WHERE GuildId = %s;",
            (guild_id,)
        )
        return [row[0] for row in await cursor.fetchall() if row]

    async def add(self, guild_id: int, word: str) -> None:
        "設定を追加します。"
        data = await self.get(guild_id, cursor=cursor)
        if word in data:
            raise Cog.BadRequest({
                "ja": "既にその言葉はNGニックネームとして追加されています。",
                "en": "The word has already been added as an NG nickname."
            })
        if len(data) >= 30:
            raise Cog.BadRequest(NO_MORE_SETTING)
        await cursor.execute(
            "INSERT INTO NgNickName VALUES (%s, %s);",
            (guild_id, word)
        )

    async def remove(self, guild_id: int, word: str) -> None:
        "設定を削除します。"
        if word in await self.get(guild_id, cursor=cursor):
            await cursor.execute("DELETE FROM NgNickName WHERE GuildId = %s;", (guild_id,))
        else:
            raise Cog.BadRequest(ALREADY_NO_SETTING)

    async def clean(self) -> None:
        "データを掃除します。"
        await self.clean_data(cursor, "NgNickName", "GuildId")


class NgNickNameEventContext(Cog.EventContext):
    "NGニックネームのイベントコンテキストです。"

    member: discord.Member


class NgNickName(Cog):
    "NGニックネームのコグです。"

    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)

    async def cog_load(self) -> None:
        await self.data.prepare_table()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick is None:
            before.nick = ""
        if after.nick:
            if before.nick != after.nick:
                for word in await self.data.get(after.guild.id):
                    if word in after.nick:
                        detail = ""
                        try:
                            await after.edit(nick=before.nick, reason=t(dict(
                                ja="NGニックネームにひっかかったため。",
                                en="Because it was caught in the NG nickname."
                            ), after.guild))
                        except discord.Forbidden:
                            detail = FORBIDDEN
                        else:
                            await after.send(
                                "<:error:878914351338246165> あなたのそのニックネームは" \
                                f"`{after.guild.name}`で有効ではありません。\n" \
                                "お手数ですが別のものにしてください。\n" \
                                f"検知した禁止ワード：`{word}`"
                            )
                        name = self.name_and_id(after)
                        self.bot.rtevent.dispatch("on_ng_nickname", NgNickNameEventContext(
                            self.bot, after.guild, self.detail_or(detail), {
                                "ja": "NGニックネーム", "en": "NG NickName"
                            }, detail or {"ja": f"メンバー：{name}", "en": f"Member: {name}"},
                            self.ngnickname
                        ))
                        break

    @commands.group(
        aliases=("ngnick", "ngnn", "NGニックネーム", "ngニックネーム", "nニック"), fsparent=FSPARENT,
        description="Register characters that cannot be used in nicknames."
    )
    async def ngnickname(self, ctx: commands.Context):
        await self.group_index(ctx)

    @ngnickname.command(aliases=ADD_ALIASES, description="Add the word of NG nick name.")
    @discord.app_commands.describe(word=(_d_w := "NG Word"))
    async def add(self, ctx: commands.Context, *, word: str):
        assert ctx.guild is not None
        async with ctx.typing():
            await self.data.add(ctx.guild.id, word)
        await ctx.reply("Ok")

    @ngnickname.command(aliases=REMOVE_ALIASES, description="Remove the word of NG nick")
    @discord.app_commands.describe(word=_d_w)
    async def remove(self, ctx: commands.Context, *, word: str):
        assert ctx.guild is not None
        async with ctx.typing():
            await self.data.remove(ctx.guild.id, word)
        await ctx.reply("Ok")

    @ngnickname.command(
        "list", aliases=LIST_ALIASES,
        description="Displays the words of NG nick"
    )
    async def list_(self, ctx: commands.Context):
        assert ctx.guild is not None
        await ctx.reply(embed=self.embed(description=", ".join(
            discord.utils.escape_markdown(word)
            for word in await self.data.get(ctx.guild.id)
        )))

    (Cog.HelpCommand(ngnickname)
        .merge_headline(ja=(_h_ja := "ニックネームとして使えない言葉を設定します。"))
        .set_description(
            ja=f"""{_h_ja}
            これで設定した言葉を使ってニックネームを使用した場合は、元々の名前に戻されるようになります。""",
            en=f"""{ngnickname.description}
            If you now use a nickname with the words you set, it will be reverted to the original name."""
        )
        .set_extra("Notes", ja="最高30個まで登録できます。", en="Up to 30 can be registered.")
        .add_sub(Cog.HelpCommand(add)
            .merge_description(ja="ニックネームとして使えない言葉を登録します。")
            .add_arg("word", "str", ja=(_d_w_ja := "NGワード"), en=_d_w))
        .add_sub(Cog.HelpCommand(remove)
            .merge_description(ja="NGニックネームの言葉を削除します。")
            .add_arg("word", "str", ja=_d_w_ja, en=_d_w))
        .add_sub(Cog.HelpCommand(list_)
            .merge_description(ja="NGニックネームとして設定されている言葉のリストを表示します。")))
    del _d_w_ja, _d_w


async def setup(bot: RT) -> None:
    await bot.add_cog(NgNickName(bot))