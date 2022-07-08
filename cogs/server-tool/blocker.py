# RT - blocker

from __future__ import annotations

from typing import Literal, TypeAlias, overload
from collections.abc import Iterator

from re import findall

from asyncio import gather

from discord.ext import commands
import discord

from core import Cog, DatabaseManager, cursor, RT, t

from rtutil.views import EmbedPage

from rtlib.common.json import loads, dumps

from data import ADD_ALIASES, REMOVE_ALIASES, LIST_ALIASES, FORBIDDEN

from .__init__ import FSPARENT


Mode: TypeAlias = Literal["emoji", "stamp", "reaction", "url"]
ModeContainAll: TypeAlias = Mode | Literal["all"]
class DataManager(DatabaseManager):
    "セーブデータを管理するためのクラスです。"

    MODES: tuple[Mode, ...] = ("emoji", "stamp", "reaction", "url")

    def __init__(self, cog: Blocker):
        # 設定のonoffだけキャッシュに入れておく。
        self.cog = cog
        self.pool = self.cog.bot.pool
        self.caches: dict[int, dict[str, list[int]]] = {}

    async def prepare_table(self) -> None:
        "テーブルを準備します。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS Blocker (
                GuildId BIGINT,
                Mode ENUM('emoji', 'stamp', 'reaction', 'url'),
                Roles JSON, Exceptions JSON
            );"""
        )
        # キャッシュを作る。
        async for row in self.fetchstep(cursor, "SELECT GuildId, Mode, Roles FROM Blocker;"):
            if row[0] not in self.caches:
                self.caches[row[0]] = {}
            self.caches[row[0]][row[1]] = loads(row[2])

    @overload
    async def toggle(self, guild_id: int, mode: Mode, **_) -> bool: ...
    @overload
    async def toggle(self, guild_id: int, mode: Literal["all"], **_) -> bool: ...
    async def toggle(self, guild_id: int, mode: ModeContainAll, **_) -> bool | tuple[bool, ...]:
        "設定のオンオフを切り替えます。"
        if mode == "all":
            return tuple(await gather(*(
                self.toggle(guild_id, mode_)
                for mode_ in self.MODES
            )))

        if guild_id not in self.caches:
            self.caches[guild_id] = {}

        if mode in self.caches[guild_id]:
            await cursor.execute(
                "DELETE FROM Blocker WHERE GuildId = %s AND Mode = %s;",
                (guild_id, mode)
            )
            del self.caches[guild_id][mode]
            if not self.caches[guild_id]:
                del self.caches[guild_id]
            return False
        else:
            await cursor.execute(
                "INSERT INTO Blocker VALUES (%s, %s, %s, %s);",
                (guild_id, mode, "[]", r"{}")
            )
            self.caches[guild_id][mode] = []
            return True

    def _is_enabled(self, guild_id: int, mode: Mode) -> None:
        if guild_id not in self.caches or mode not in self.caches[guild_id]:
            raise Cog.BadRequest({
                "ja": "先にブロッカーの機能を有効にしてください。",
                "en": "Please enable the blocker function first."
            })

    async def add_role(self, guild_id: int, mode: ModeContainAll, role_id: int, **_) -> None:
        "ロールを追加します。"
        if mode == "all":
            await gather(*(
                self.add_role(guild_id, mode_, role_id)
                for mode_ in self.MODES
            ))
            return

        self._is_enabled(guild_id, mode)
        if mode in self.caches[guild_id] and (
            role_id in self.caches[guild_id] or len(self.caches[guild_id][mode]) > 15
        ):
            raise Cog.BadRequest({
                "ja": "既に登録しているまたはこれ以上設定できません。",
                "en": "Already registered or cannot be set any further."
            })
        else:
            self.caches[guild_id][mode].append(role_id)
            await cursor.execute(
                "UPDATE Blocker SET Roles = %s WHERE GuildId = %s AND Mode = %s;",
                (dumps(self.caches[guild_id][mode]), guild_id, mode)
            )

    @overload
    async def remove_role(
        self, guild_id: int, mode: Literal["all"],
        role_id: int, **_
    ) -> Iterator[Exception]: ...
    @overload
    async def remove_role(self, guild_id: int, mode: Mode, role_id: int, **_) -> None: ...
    async def remove_role(
        self, guild_id: int, mode: ModeContainAll, role_id: int, **_
    ) -> None | Iterator[Exception]:
        "ロールを削除します。"
        if mode == "all":
            return filter(lambda r: isinstance(r, Exception), await gather(*(
                self.remove_role(guild_id, mode_, role_id)
                for mode_ in self.MODES
            ), return_exceptions=True))

        self._is_enabled(guild_id, mode)
        if role_id not in self.caches[guild_id][mode]:
            raise Cog.BadRequest({
                "ja": "そのロールは設定されていません。",
                "en": "That role is not set."
            })

        await cursor.execute(
            "UPDATE Blocker SET Roles = %s WHERE GuildId = %s AND Mode = %s;",
            (dumps(self.caches[guild_id][mode]), guild_id, mode)
        )
        self.caches[guild_id][mode].remove(role_id)

    async def clean(self):
        "データを掃除します。"
        for guild_id in list(self.caches.keys()):
            if await self.cog.bot.exists("guild", guild_id):
                continue
            for mode in self.MODES:
                await cursor.execute(
                    "DELETE FROM Blocker WHERE GuildId = %s AND Mode = %s;",
                    (guild_id, mode)
                )
                del self.caches[guild_id]


class BlockerEventContext(Cog.EventContext):
    "ブロッカー機能で何かを削除したときのベースイベントコンテキストです。"

    author: discord.Member
    additional: discord.Message | discord.Reaction


class Blocker(Cog):
    "ブロッカー機能のコグです。"

    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)

    MODES_JA = {
        "stamp": "スタンプ", "emoji": "絵文字",
        "reaction": "リアクション", "url": "URL",
        "all": "すべての"
    }

    async def cog_load(self) -> None:
        await self.data.prepare_table()

    @commands.group(
        aliases=("block", "ブロッカー"), fsparent=FSPARENT,
        description="Block sending emojj/stamp."
    )
    @commands.has_guild_permissions(administrator=True)
    async def blocker(self, ctx: commands.Context):
        await self.group_index(ctx)

    _HELP = Cog.HelpCommand(blocker) \
        .merge_description("headline", ja="絵文字やスタンプの送信を防止します。")

    @blocker.command(
        "list", aliases=LIST_ALIASES,
        description="Displays a list of blocker settings."
    )
    async def list_(self, ctx: commands.Context):
        assert ctx.guild is not None
        if ctx.guild.id not in self.data.caches:
            return await ctx.reply(t(dict(
                ja="ブロッカーが有効ではありません。",
                en="The blocker is not effective."
            ), ctx))

        await EmbedPage([
            Cog.Embed(t(dict(
                ja=f"{self.MODES_JA[mode]}ブロッカーの設定",
                en=f"Settings of {mode} blocker"
            ), ctx), description=", ".join(f"<@&{role_id}>" for role_id in role_ids))
            for mode, role_ids in self.data.caches[ctx.guild.id].items()
        ]).first_reply(ctx)

    _HELP.add_sub(Cog.HelpCommand(list_)
        .set_description(
            ja="ブロッカーに設定されているロールƒ"
        ))

    @blocker.command(description="Toggle blocker.")
    @discord.app_commands.describe(mode="Blocking type")
    async def toggle(self, ctx, mode: ModeContainAll):
        result = await self.data.toggle(ctx.guild.id, mode)
        if isinstance(result, tuple):
            return await ctx.reply(t(dict(
                ja="全機能の設定を反転しました。",
                en="Inverted settings of all blocker."
            ), ctx))
        await ctx.reply(t(dict(
            ja=f"{self.MODES_JA[mode]}ブロッカーを{'有効化' if result else '無効化'}しました。",
            en=f"{'Enabled' if result else 'Disabled'} {mode} blocker."
        ), ctx))

    _HELP.add_sub(Cog.HelpCommand(toggle)
        .merge_description("headline", ja="ブロッカーのオンオフを切り替えます。")
        .add_arg("mode", "str", ja=(_c_d_ja := "ブロックする種類"), en=(_c_d := "Blocking type"))
        .set_extra("Notes",
            ja="modeにallを指定すると全ての種類のブロッカー(絵文字、スタンプ、リアクション)に適用します。\n"
               "その場合全機能の設定が反転しますので実行は最初に設定を確認してからをお勧めします。\n"
               "また、全てのコマンドに対して`all`は使用可能です。",
            en="If `all` set to mode, Changes will be applied to all types of blocker(emoji, stamp, reaction).\n"
               "In that case, All settings will be inverted so you had better check settings at first.\n"
               "Also, you can use `all` for all commands."))

    @blocker.group(description="Set blocking roles.")
    async def role(self, ctx):
        await self.group_index(ctx)

    _HELP.add_sub(Cog.HelpCommand(role)
        .merge_description("headline", ja="ブロックするロールを指定できます。"))

    @role.command(aliases=ADD_ALIASES, description="Add Blocking Roles.")
    @discord.app_commands.describe(mode="Blocking type", role="Adding role")
    async def add(self, ctx, mode: ModeContainAll, *, role: discord.Role):
        async with ctx.typing():
            await self.data.add_role(ctx.guild.id, mode, role.id)
        await ctx.reply("Ok")

    _HELP.add_sub(Cog.HelpCommand(add)
        .merge_description("headline", ja="ブロックするロールを追加できます。")
        .add_arg("mode", "str", ja=_c_d_ja, en=_c_d)
        .add_arg("role", "Role", ja="追加するロール", en=(_c_d2 := "Adding role")))

    @role.command(aliases=REMOVE_ALIASES, description="Remove Blocking Roles.")
    @discord.app_commands.describe(mode="Blocking type", role="Removing role")
    async def remove(self, ctx, mode: ModeContainAll, *, role: discord.Role):
        async with ctx.typing():
            result = await self.data.remove_role(ctx.guild.id, mode, role.id)
        await ctx.reply(t(dict(
            ja="設定を試みて、{length}回設定に失敗しました。",
            en="Attempted to set and failed to set {length} times."
        ), ctx, length=len(set(result))) if result else "Ok")

    _HELP.add_sub(Cog.HelpCommand(remove)
        .merge_description("headline", ja="ブロックするロールを削除します。")
        .add_arg("mode", "str", ja=_c_d_ja, en=_c_d)
        .add_arg("role", "Role", ja="削除するロール", en=_c_d2.replace("Add", "Remov")))

    async def call_after(
        self, guild: discord.Guild, author: discord.Member, mode: Mode,
        additional: discord.Message | discord.Reaction,
        error_: Exception | None = None
    ) -> None:
        "ブロッカー用のRTイベントを発行します。それと、送信者にブロックしたことを伝えます。"
        try:
            await author.send(t(dict(
                ja=f"{self.MODES_JA[mode]}は{{guild_name}}で禁止されています。",
                en=f"{mode} is blocked content on {{guild_name}}."
            ), author, guild_name=guild.name))
        except Exception:
            ...

        error = None
        if isinstance(error_, discord.Forbidden):
            error = FORBIDDEN
        self.bot.rtevent.dispatch("on_blocker", BlockerEventContext(
            self.bot, guild, error, {
                "ja": "コンテンツブロッカー", "en": "Content Blocker"
            }, self.text_format({
                "ja": f"種類：{self.MODES_JA[mode]}\n実行者：{{author}}",
                "en": f"Mode: {mode}\nAuthor: {{author}}"
            }, author=self.name_and_id(author)),
            additional=additional, author=author
        ))

    def is_target(self, guild_id: int, author: discord.Member, mode: Mode) -> bool:
        "ブロッカーのチェックが必要かどうかを返します。"
        return mode in self.data.caches[guild_id] and any(
            author.get_role(role_id) is not None
            for role_id in self.data.caches[guild_id][mode]
        )

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot \
                or not isinstance(message.author, discord.Member) \
                or message.guild.id not in self.data.caches:
            return

        # 絵文字とURLとスタンプのブロッカーのチェックを行う。
        for mode in self.data.MODES:
            if self.is_target(message.guild.id, message.author, mode) and (
                (mode == "emoji" and findall(r"<a?:\w+:\d*>", message.content))
                or (mode == "url" and findall(r"https?://.*", message.content))
                or (mode == "stamp" and message.stickers)
            ):
                error = None
                try:
                    await message.delete()
                except Exception as e:
                    error = e
                await self.call_after(message.guild, message.author, mode, message, error)

    @Cog.listener()
    async def on_reaction_add(
        self, reaction: discord.Reaction, user: discord.Member | discord.User
    ):
        if user.bot or reaction.message.guild is None or not isinstance(user, discord.Member) \
                or reaction.message.guild.id not in self.data.caches:
            return

        # リアクションのブロッカーのチェックを行う。
        if self.is_target(reaction.message.guild.id, user, "reaction"):
            error = None
            try:
                await reaction.message.remove_reaction(reaction.emoji, user)
            except Exception as e:
                error = e
            await self.call_after(reaction.message.guild, user, "reaction", reaction, error)

    del _HELP, _c_d, _c_d2, _c_d_ja


async def setup(bot: RT):
    await bot.add_cog(Blocker(bot))