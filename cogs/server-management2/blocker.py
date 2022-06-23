# RT - blocker

from __future__ import annotations

from typing import Literal, TypeAlias

from discord.ext import commands
import discord

from collections import defaultdict
from re import findall

from core import Cog, DatabaseManager, cursor, RT
from core.views import EmbedPage

from rtlib.common.json import loads, dumps
from rtlib.common.cacher import Cacher

from data import ADD_ALIASES, REMOVE_ALIASES, FORBIDDEN

from .__init__ import FSPARENT


class DataManager(DatabaseManager):

    MODES = ("emoji", "stamp", "reaction", "url")
    Modes: TypeAlias = Literal["emoji", "stamp", "reaction", "url", "all"]

    def __init__(self, cog: Blocker):
        # 設定のonoffだけキャッシュに入れておく。
        self.cog = cog
        self.onoff_cache = defaultdict(dict)
        self.cache: Cacher = self.cog.bot.cachers.acquire(30.0)  # 荒らし防止用キャッシュ

    async def prepare_table(self) -> None:
        "テーブルを準備します。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS Blocker(
                GuildId BIGINT PRIMARY KEY NOT NULL,
                Mode ENUM('emoji', 'stamp', 'reaction', 'url'),
                Blocking BOOLEAN, Roles JSON, Exceptions JSON
            );"""
        )
        async for row in self.fetchstep(cursor, "SELECT GuildId, Mode, Blocking FROM Blocker;"):
            self.onoff_cache[row[0]][row[1]] = row[2]

    async def toggle(self, guild_id: int, mode: Modes, **_) -> bool | tuple[bool, bool, bool]:
        "設定のオンオフを切り替えます。"
        if mode == "all":
            return (await self.toggle(guild_id, mo, cursor=cursor) for mo in self.MODES)

        if guild_id not in self.onoff_cache:
            await cursor.execute(
                f"INSERT INTO Blocker VALUES (%s, %s, 1, %s, %s)",
                (guild_id, mode, "[]", "{}")
            )
            self.onoff_cache[guild_id][mode] = True
            return True

        onoff = not self.onoff_cache[guild_id][mode]
        await cursor.execute(
            "UPDATE Blocker Blocking = %s WHERE GuildId = %s",
            (onoff, guild_id)
        )
        self.onoff_cache[guild_id][mode] = onoff
        return onoff

    async def add_role(self, guild_id: int, mode: Modes, role_id: int, **_) -> None:
        "ロールを追加します。"
        if mode == "all":
            await self.add_role(guild_id, mo, role_id, cursor=cursor) for mo in self.MODES
            return

        if role_id in (now := self.get_now_roles(guild_id, mode, cursor=cursor)) or len(now) > 15:
            raise ValueError("既に登録しているまたはこれ以上設定できません。")

        await cursor.execute(
            """INSERT INTO Blocker VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE Roles = %s;""",
            (guild_id, mode, False, dumps([role_id]), "[]",
                dumps(now + [role_id]))
        )

    async def remove_role(
        self, guild_id: int, mode: Modes, role_id: int, **_
    ) -> list[Modes] | None:
        """ロールを削除します。未設定orそのロールが設定されていない場合はValueErrorを送出します。
        table引数が`all`だった場合には削除に成功したテーブルのリストを返します。"""
        if mode == "all":
            succeed = []
            for mode in self.MODES:
                try: await self.remove_role(guild_id, mode, role_id, cursor=cursor)
                except ValueError: pass
                else: succeed.append(mo)
            return succeed

        if not (now := self.get_now_roles(guild_id, mode, cursor=cursor)) or role_id not in now:
            raise ValueError("そのロールは設定されていません。")

        now.remove(guild_id)
        await cursor.execute(
            """UPDATE Blocker SET Roles = %s WHERE GuildId = %s AND Mode = %s;""",
            (dumps(now), guild_id, mode)
        )

    async def get_settings(
        self, guild_id: int, mode: Modes, targets: str | None = None, **_
    ) -> tuple:
        "設定を取得します。targetsが指定されていなければ全て返します。"
        if mode == "all":
            return (await self.get_settings(guild_id, mo, targets, cursor=cursor)
                    for mo in self.MODES)
        await cursor.execute(
            f"""SELECT {targets or '*'} FROM Blocker
                WHERE GuildId = %s AND Mode = %s LIMIT 1;""",
            (guild_id, mode)
        )
        return await cursor.fetchone()

    async def get_now_roles(self, guild_id: int, mode: Modes, **_) -> list[int]:
        "現在のロール設定を取得します。設定されていない場合は[]です。"
        if (g := guild_id in self.cache.data) and mode in self.cache[guild_id].data:
            return self.cache[guild_id].data[mode]
        now_roles = self.get_settings(guild_id, mode, "Roles", cursor=cursor)
        roles = loads(now_roles[0][0]) if now_roles else []
        self.cache.set(guild_id, self.cache[guild_id].data + {mode: roles} if g else {mode: roles})
        return roles

    async def clean(self):
        "データを掃除します。"
        for guild_id in self.onoff_cache:
            if await self.bot.exists("guild", guild_id):
                continue
            for mode in self.MODES:
                await cursor.execute(
                    "DELETE FROM Blocker WHERE GuildId = %s AND Mode = %s;",
                    (guild_id, mode)
                )


class BlockerDeleteEventContext(Cog.EventContext):
    "ブロッカー機能で何かを削除したときのベースイベントコンテキストです。"

    channel: discord.TextChannel | None
    message: discord.Message | None
    member: discord.Member | None
class BlockerDeleteEmojiEventContext(BlockerDeleteEventContext):
    "ブロッカー機能で絵文字を削除したときのイベントコンテキストです。"

    emoji: discord.Emoji | str | None
class BlockerDeleteStampEventContext(BlockerDeleteEventContext):
    "ブロッカー機能でスタンプを削除したときのイベントコンテキストです。"

    stamp: discord.Sticker | discord.StickerItem | None
class BlockerDeleteReactionEventContext(BlockerDeleteEventContext):
    "ブロッカー機能でリアクションを削除したときのイベントコンテキストです。"

    reaction: discord.Reaction | None
class BlockerDeleteUrlEventContext(BlockerDeleteEventContext):
    "ブロッカー機能でリンクを削除したときのイベントコンテキストです。"

    url: str | None


class Blocker(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)

    MODES_JA = {
        "stamp": "スタンプ",
        "emoji": "絵文字",
        "reaction": "リアクション",
        "url": "URL",
        "all": "すべての"
    }

    async def cog_load(self) -> None:
        await self.data.prepare_table()

    @commands.group(aliases=("block", "ブロッカー"), description="Block sending emojj/stamp.", fsparent=FSPARENT)
    @commands.has_guild_permissions(administrator=True)
    async def blocker(self, ctx):
        if ctx.invoked_subcommand: return

        embeds = []
        for mo in self.data.MODES:
            se = await self.data.get_settings(ctx.guild.id, mo, "Blocking, Roles")
            # 今後例外機能を追加する場合はExceptionsを処理する。

            embed = Cog.Embed(t(dict(
                ja=f"{MODES_JA[mo]}ブロッカーの設定", en=f"Settings of {mo} blocker"
            ), ctx), description=t(dict(
                ja="設定されていません。", en="Not setting."
            ), ctx) if not se else t(dict(
                ja="オン" if se[0][0] else "オフ", en="ON" if se[0][0] else "OFF"
            ), ctx))

            if not se or se[0][0]:
                continue  # 設定されていなかった場合。
            embed.add_field(
                name=t({"ja": "設定済みロール", "en": "Setting Roles"}, ctx),
                value=", ".join(ctx.guild.get_role(r).mention for r in se[0][1]) or "..."
            )
            embeds.append(embed)

        view = EmbedPage(embeds)
        m = await ctx.reply(embed=embeds[0], view=view)
        view.set_message(m)

    _HELP = Cog.HelpCommand(blocker) \
        .merge_description("headline", ja="絵文字やスタンプの送信を防止します。")

    @blocker.command(description="Toggle blocker.")
    @discord.app_commands.describe(mode=(_c_d := "Blocking type"))
    async def toggle(self, ctx, mode: DataManager.Modes):
        result = await self.data.toggle(ctx.guild.id, mode)
        if isinstance(result, tuple):
            return await ctx.reply(t(dict(
                ja="全機能の設定を反転しました。",
                en="Inverted settings of all blocker."
            ), ctx))
        await ctx.reply(t(dict(
            ja=f"{self.MODES_JA[mode]}を{'有効化' if result else '無効化'}しました。",
            en=f"{'Enabled' if result else 'Disabled'} {mode} blocker."
        ), ctx))

    _HELP.add_sub(Cog.HelpCommand(toggle)
        .merge_description("headline", "ブロッカーのオンオフを切り替えます。")
        .add_arg("mode", "str", ja=(_c_d_ja := "ブロックする種類"), en=_c_d)
        .set_extra("Notes",
            ja="modeにallを指定すると全ての種類のブロッカー(絵文字、スタンプ、リアクション)に適用します。\n"
               "その場合全機能の設定が反転しますので実行は最初に設定を確認してからをお勧めします。\n"
               "また、全てのコマンドに対して`all`は使用可能です。",
            en="If `all` set to mode, Changes will be applied to all types of blocker(emoji, stamp, reaction).\n"
               "In that case, All settings will be inverted so you had better check settings at first.\n"
               "Also, you can use `all` for all commands."))

    @blocker.group(description="Set blocking roles.")
    async def role(self, ctx):
        pass

    _HELP.add_sub(Cog.HelpCommand(role)
        .merge_description("headline", "ブロックするロールを指定できます。"))

    @role.command(aliases=ADD_ALIASES, description="Add Blocking Roles.")
    @discord.app_commands.describe(mode="Blocking type", role=(_c_d2 := "Adding role"))
    async def add(self, ctx, mode: DataManager.Modes, role: discord.Role):
        try:
            self.data.add_role(ctx.guild.id, mode, role.id)
        except ValueError as e:
            raise Cog.BadRequest(t(dict(
                ja=e.args[0], en="Already set this role or you can't set more."
            ), ctx))
        await ctx.reply("Ok")

    _HELP.add_sub(Cog.HelpCommand(add)
        .merge_description("headline", "ブロックするロールを追加できます。")
        .add_arg("mode", "str", ja=_c_d_ja, en=_c_d)
        .add_arg("role", "Role", ja="追加するロール", en=_c_d2))

    @role.command(aliases=REMOVE_ALIASES, description="Remove Blocking Roles.")
    @discord.app_commands.describe(mode="Blocking type", role=(_c_d2 := "Removing role"))
    async def remove(self, ctx, mode: DataManager.Modes, role: discord.Role):
        try:
            result = self.data.remove_role(ctx.guild.id, mode, role.id)
        except ValueError as e:
            raise Cog.BadRequest(t(dict(
                ja=e.args[0], en="The role wasn't set."
            ), ctx))
        if result:
            await ctx.reply(t(dict(
                ja=f"{'ブロッカー, '.join(self.MODES_JA[mode] for mode in result)}ブロッカーのそのロールの設定を解除しました。"
                   if len(result) != 0 else "どのブロッカーもそのロールは設定していませんでした。",
                en=f"Removed that role setting of {' blocker, '.join(self.MODES_JA[mode] for mode in result)}blocker."
                   if len(result) != 0 else "Any type of blocker didn't set the role."
            )))
        else:
            await ctx.reply("Ok")

    _HELP.add_sub(Cog.HelpCommand(remove)
        .merge_description("headline", "ブロックするロールを削除します。")
        .add_arg("mode", "str", ja=_c_d_ja, en=_c_d)
        .add_arg("role", "Role", ja="削除するロール", en=_c_d2))

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if (not message.guild or message.author.bot or not isinstance(message.author, discord.Member)
            or message.guild.id not in self.data.onoff_cache
                or all(not m for m in self.data.onoff_cache[message.guild.id].values())):
            return

        async def sender(mode):
            await message.channel.send(t(dict(
                ja=f"{self.MODES_JA[mode]}の送信はサーバーの管理者により禁止されています。",
                en=f"Sending {mode} is forbidden by server administrator."
            ), message), delete_after=5.0)

        error = None
        if c := findall(r"<a?:\w+:\d*>", message.content):
            # 絵文字ブロッカー
            if self.data.onoff_cache[message.guild.id].get("emoji", False) and any(
                c in message.author.roles 
                for c in self.data.get_now_roles(message.guild.id, "Emoji")
            ):
                try:
                    await message.delete()
                    await sender("emoji")
                except discord.Forbidden:
                    error =  FORBIDDEN
                except discord.HTTPException:
                    error = {"ja": "なんらかのエラーが発生しました。", "en": "Something went wrong."}
                self.bot.rtevent.dispatch("on_delete_message_emoji_blocker",
                    BlockerDeleteEmojiEventContext(
                        self.bot, message.guild, self.detail_or(error),
                        {"ja": "絵文字ブロッカー", "en": "Emoji blocker"},
                        {"ja": f"ユーザー:{message.author}", "en": f"User: {message.author}"},
                        self.blocker, channel=message.channel, message=message, member=message.author,
                        emoji=discord.utils.get(message.guild.roles, name=c[0].split(":")[1]) or c[0]
                ))
                return
        if c := message.stickers:
            # スタンプブロッカー
            if self.data.onoff_cache[message.guild.id].get("stamp", False) and any(
                c in message.author.roles 
                for c in self.data.get_now_roles(message.guild.id, "Stamp")
            ):
                try:
                    await message.delete()
                    await sender("stamp")
                except discord.Forbidden:
                    error =  FORBIDDEN
                except discord.HTTPException:
                    error = {"ja": "なんらかのエラーが発生しました。", "en": "Something went wrong."}
                self.bot.rtevent.dispatch("on_delete_message_stamp_blocker",
                    BlockerDeleteStampEventContext(
                        self.bot, message.guild, self.detail_or(error),
                        {"ja": "スタンプブロッカー", "en": "Stamp blocker"},
                        {"ja": f"ユーザー:{message.author}", "en": f"User: {message.author}"},
                        self.blocker, channel=message.channel, message=message, member=message.author,
                        stamp=c
                ))
                return
        if c := findall(r"https?://.*", message.content):
            # URLブロッカー
            if self.data.onoff_cache[message.guild.id].get("url", False) and any(
                c in message.author.roles 
                for c in self.data.get_now_roles(message.guild.id, "url")
            ):
                try:
                    await message.delete()
                    await sender("url")
                except discord.Forbidden:
                    error =  FORBIDDEN
                except discord.HTTPException:
                    error = {"ja": "なんらかのエラーが発生しました。", "en": "Something went wrong."}
                self.bot.rtevent.dispatch("on_delete_message_url_blocker",
                    BlockerDeleteUrlEventContext(
                        self.bot, message.guild, self.detail_or(error),
                        {"ja": "URLブロッカー", "en": "Url blocker"},
                        {"ja": f"ユーザー:{message.author}", "en": f"User: {message.author}"},
                        self.blocker, channel=message.channel, message=message, member=message.author,
                        url=c[0]
                ))

    @Cog.listener()
    async def on_reaction_add(self, reaction):
        if (not reaction.guild or reaction.author.bot or not isinstance(reaction.author, discord.Member)
            or reaction.guild.id not in self.data.onoff_cache
                or not self.data.onoff_cache[reaction.guild.id].get("reaction", False)):
            return
        if any(c in reaction.author.roles 
            for c in self.data.get_now_roles(reaction.guild.id, "reaction")
        ):
            await reaction.channel.send(t(dict(
                ja="リアクションの追加はサーバーの管理者により禁止されています。",
                en="Adding reaction is forbidden by server administrator."
            ), reaction.author), delete_after=5.0)
            self.bot.rtevent.dispatch("on_delete_reaction_stamp_blocker",
                BlockerDeleteReactionEventContext(
                    self.bot, reaction.guild, self.detail_or(error),
                    {"ja": "スタンプブロッカー", "en": "Stamp blocker"},
                    {"ja": f"ユーザー:{reaction.author}", "en": f"User: {reaction.author}"},
                    self.blocker, channel=reaction.message.channel, message=reaction.message, 
                    member=reaction.author, reaction=reaction
            ))
    
    del _HELP, _c_d, _c_d2, _c_d_ja


async def setup(bot: RT):
    await bot.add_cog(Blocker(bot))
