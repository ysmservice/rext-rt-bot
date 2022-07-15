# RT - Role Linker

from __future__ import annotations

from typing import NoReturn, TypeAlias, NamedTuple, Literal

from collections import defaultdict

from discord.ext import commands, tasks
import discord

from jishaku.functools import executor_function

from core import Cog, RT, t, DatabaseManager, cursor

from rtlib.common.cacher import Cacher

from data import (
    ADD_ALIASES, REMOVE_ALIASES, LIST_ALIASES,
    NO_MORE_SETTING, FORBIDDEN, ROLE_NOTFOUND
)

from .__init__ import FSPARENT


Data = NamedTuple("Data", (
    ("guild_id", int), ("before", int),
    ("after", int), ("reverse", bool)
))
Datas: TypeAlias = defaultdict[int, list[Data]]


class LoopChecker:
    "ループをチェックします。"

    def __init__(self, datas: Datas):
        self.datas = datas
        self.checked: dict[int, list[int]] = defaultdict(list)

    def reset(self) -> None:
        self.checked = defaultdict(list)

    def walk(self, attempt: int, key: int) -> None:
        if key in self.checked[attempt]:
            raise OverflowError("ループを検知しました。")
        self.checked[attempt].append(key)
        if key in self.datas:
            for data in self.datas[key]:
                self.walk(attempt, data.after)

    @executor_function
    def validate(self) -> None | NoReturn:
        "ループがないかを調べます。"
        self.reset()
        for attempt, key in enumerate(self.datas):
            self.walk(attempt, key)


class DataManager(DatabaseManager):
    "データ管理用のクラスです。"

    def __init__(self, cog: RoleLinker):
        self.cog = cog
        self.pool = self.cog.bot.pool
        self.caches: Cacher[int, Datas] = \
            self.cog.bot.cachers.acquire(1800.0, lambda: defaultdict(list))

    async def prepare_table(self) -> None:
        "テーブルを作ります。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS RoleLinker (
                GuildId BIGINT, BeforeId BIGINT,
                AfterId BIGINT, IsReverse BOOLEAN
            );"""
        )

    async def read(self, guild_id: int, **_) -> Datas:
        "データを読み込みます。"
        if guild_id not in self.caches:
            await cursor.execute(
                "SELECT * FROM RoleLinker WHERE GuildId = %s;",
                (guild_id,)
            )
            for row in filter(lambda x: bool(x), await cursor.fetchall()):
                self.caches[guild_id][row[1]].append(Data(*row[:-1], bool(row[-1]))) # type: ignore
        return self.caches[guild_id]

    MAX = 30

    async def write(
        self, guild_id: int, before: int,
        after: int, reverse: bool = True
    ) -> None | dict[str, str]:
        "データを書き込みます。"
        datas = await self.read(guild_id, cursor=cursor)
        if datas:
            for data in datas[before]:
                if before in datas and data.after == after:
                    return {
                        "ja": "既に同じロールの設定が存在しています。",
                        "en": "The same settings of the role already exist."
                    }
        if self.MAX <= sum(len(datas) for datas in self.caches[guild_id].values()):
            return NO_MORE_SETTING
        row = (guild_id, before, after, reverse)
        self.caches[guild_id][before].append(Data(*row))
        # ループが起きないかをチェックする。
        try:
            await LoopChecker(datas).validate()
        except OverflowError:
            del self.caches[guild_id][before][-1]
            return {
                "ja": "ループが発生する可能性があったので設定を中止しました。",
                "en": "The setting was discontinued because of the possibility of a loop."
            }
        await cursor.execute("INSERT INTO RoleLinker VALUES (%s, %s, %s, %s);", row)

    async def delete(self, guild_id: int, before: int, after: int, **_) -> None:
        "データを書き込みます。"
        await cursor.execute(
            "DELETE FROM RoleLinker WHERE GuildId = %s AND BeforeId = %s AND AfterId = %s;",
            (guild_id, before, after)
        )
        if guild_id in self.caches and before in self.caches[guild_id]:
            for index, data in enumerate(self.caches[guild_id][before]):
                if data.after == after:
                    del self.caches[guild_id][before][index]
                    break

    async def clean(self) -> None:
        "データをお掃除します。"
        guild, did = None, []
        async for row in self.fetchstep(cursor, "SELECT * FROM RoleLinker;"):
            if row[0] in did:
                continue
            if guild is None or guild.id != row[0]:
                if not self.cog.bot.exists("guild", row[0]):
                    await cursor.execute("DELETE FROM RoleLinker WHERE GuildId = %s;", row[:1])
                    if row[0] in self.caches:
                        del self.caches[row[0]]
                    did.append(row[0])
                    continue
                guild = self.cog.bot.get_guild(row[0])
            if guild is None:
                did.append(row[0])
            else:
                if guild.get_role(row[1]) is None or guild.get_role(row[2]):
                    await self.delete(*row[:3], cursor=cursor)
        await self.cog.bot.censor(cursor, "RoleLinker", self.MAX)


class RoleLinkerEventContext(Cog.EventContext):
    member: discord.Member
    add_roles: list[discord.Role]
    remove_roles: list[discord.Role]


Queues: TypeAlias = defaultdict[discord.Member, tuple[list[discord.Role], list[discord.Role]]]
class RoleLinker(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)
        self.queues: Queues = defaultdict(lambda: ([], []))

    @commands.group(
        aliases=("rl", "ロールリンカー"), fsparent=FSPARENT,
        description="Tie the roles to the roles."
    )
    @commands.has_guild_permissions(manage_roles=True)
    @commands.cooldown(1, 8, commands.BucketType.guild)
    async def role_linker(self, ctx: commands.Context):
        await self.group_index(ctx)

    @role_linker.command(
        aliases=ADD_ALIASES,
        description="Add roleLink setting"
    )
    @discord.app_commands.describe(
        reverse="Whether to do the opposite of what happened to the monitored role.",
        before=(_d_b := "The monitored role to be triggered."),
        after=(_d_a := "A role to add or remove.")
    )
    async def add(
        self, ctx: commands.Context, reverse: bool,
        before: discord.Role, *, after: discord.Role
    ):
        await ctx.typing()
        assert ctx.guild is not None
        await ctx.reply(t(
            await self.data.write(ctx.guild.id, before.id, after.id, reverse)
            or {"ja": "Ok"}, ctx
        ))

    @role_linker.command(
        aliases=REMOVE_ALIASES,
        description="Remove roleLink setting"
    )
    @discord.app_commands.describe(before=_d_b, after=_d_a)
    async def remove(self, ctx: commands.Context, before: discord.Role, *, after: discord.Role):
        await ctx.typing()
        assert ctx.guild is not None
        await self.data.delete(ctx.guild.id, before.id, after.id)
        await ctx.reply("Ok")

    @role_linker.command("list", aliases=LIST_ALIASES, description="Displays roleLink setting")
    async def list_(self, ctx: commands.Context):
        await ctx.typing()
        assert ctx.guild is not None
        all_data = await self.data.read(ctx.guild.id)
        reverse = t(dict(ja="リバースモード：%s", en="ReverseMode: %s"), ctx)
        await ctx.reply(embed=self.embed(description="".join("\n".join(
            f"・<@&{before}>：<@&{data.after}>, {reverse % data.reverse}"
            for data in datas
        ) for before, datas in all_data.items())))

    (Cog.HelpCommand(role_linker)
        .merge_headline(ja="ロールとロールを紐づけます。")
        .set_description(
            ja="""ロールとロールを紐づけます。
                例えばとあるロールが付与された際に別のロールも付与するといったようなものです。
                また、その逆のロールが付与された際に別のロールを削除するということもできます。""",
            en=f"""{role_linker.description}
                For example, when one role is added, another role is added.
                And, the reverse can be done. (When one role is added, another role is removed.)"""
        )
        .for_customer()
        .set_extra("Notes",
            ja="Discordにやりすぎと言われないようにロールの付与と削除は五秒以上遅れることがあります。",
            en="Adding and removing roles can be delayed for more than five seconds so that Discord does not say you are overdoing it.")
        .add_sub(Cog.HelpCommand(add)
            .set_description(ja="ロールリンクの設定を追加します。", en=add.description)
            .add_arg("reverse", "bool",
                ja="監視されたロールに起きたことと反対のことを行うかどうか。",
                en=add.description)
            .add_arg("before", "Role",
                ja="トリガーとなる監視対象のロールです。", en=_d_b)
            .add_arg("after", "Role",
                ja="付与または削除を行うロールです。", en=_d_a))
        .add_sub(Cog.HelpCommand(remove)
            .set_description(ja="ロールリンクの設定を削除します。", en=remove.description)
            .add_arg("before", "Role",
                ja="トリガーとなる監視対象のロールです。", en=_d_b)
            .add_arg("after", "Role",
                ja="付与または削除を行うロールです。", en=_d_a))
        .add_sub(Cog.HelpCommand(list_)
            .set_description(ja="ロールリンクの設定を表示します。", en=list_.description)))
    del _d_b, _d_a

    async def cog_load(self):
        await self.data.prepare_table()
        self.queue_processer.start()

    async def cog_unload(self):
        self.queue_processer.cancel()

    @commands.Cog.listener()
    async def on_member_role_add(self, member: discord.Member, role: discord.Role):
        await self.on_member_role_change("add", member, role)

    @commands.Cog.listener()
    async def on_member_role_remove(self, member: discord.Member, role: discord.Role):
        await self.on_member_role_change("remove", member, role)

    async def on_member_role_change(
        self, mode: Literal["add", "remove"], member: discord.Member,
        role: discord.Role
    ):
        # キューに追加/付与を行うロールを追加する。
        datas = await self.data.read(member.guild.id)
        if role.id in datas:
            for data in datas[role.id]:
                add = data.reverse
                if mode == "add":
                    add = not add
                add = int(add) - 1
                if role not in self.queues[member][add]:
                    if (after_role := member.guild.get_role(data.after)) is None:
                        raise ValueError("NotFound")
                    self.queues[member][add].append(after_role)

    async def _manage_roles(
        self, mode: Literal["add", "remove"], member: discord.Member,
        roles: list[discord.Role]
    ) -> None:
        # ロールの付与/削除を行う。
        roles = roles = list(filter(lambda role:
            (mode == "add" and member.get_role(role.id) is None)
            or (mode == "remove" and member.get_role(role.id) is not None),
        roles))
        self.queues[member] = ([], self.queues[member][1]) if mode == "add" \
            else (self.queues[member][0], [])
        if roles:
            await getattr(member, f"{mode}_roles")(*roles, reason=t(dict(
                ja=f"ロールリンカーのロールの{'付与' if mode == 'add' else '削除'}",
                en=f"RoleLinker's {mode}"
            ), member.guild))

    @tasks.loop(seconds=5)
    async def queue_processer(self):
        # ロールの付与/削除のキューにあるロールの処理をする。
        for member, (add_roles, remove_roles) in list(self.queues.items()):
            detail = ""
            try:
                if add_roles:
                    await self._manage_roles("add", member, add_roles)
                if remove_roles:
                    await self._manage_roles("remove", member, remove_roles)
            except discord.Forbidden:
                detail = FORBIDDEN
            except ValueError:
                detail = ROLE_NOTFOUND
            if add_roles or remove_roles:
                self.bot.rtevent.dispatch("on_role_linker_process", RoleLinkerEventContext(
                    self.bot, member.guild, "ERROR" if detail else "SUCCESS", {
                        "ja": "ロールリンカーのリンク", "en": "RoleLinker's link"
                    }, detail or {
                        "ja": "ロールリンカーのロール付与/削除", "en": "Roll linker rolls granted/removed"
                    }, self.role_linker, member=member,
                    add_roles=add_roles, remove_roles=remove_roles
                ))


async def setup(bot: RT) -> None:
    await bot.add_cog(RoleLinker(bot))