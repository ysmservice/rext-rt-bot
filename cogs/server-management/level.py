# RT - Level

from __future__ import annotations

from dataclasses import dataclass

from discord.ext import commands, tasks
import discord

from core import Cog, RT, t, DatabaseManager, cursor

from rtlib.common.cacher import Cacher

from data import (
    ROLE_NOTFOUND, FORBIDDEN, SET_ALIASES, DELETE_ALIASES,
    LIST_ALIASES, SHOW_ALIASES, TOO_SMALL_OR_LARGE_NUMBER
)

from .__init__ import FSPARENT


def calculate(level: int) -> int:
    "指定されたレベルに必要なメッセージ数を計算します。"
    return (2 * level) ** 2


@dataclass
class LevelData:
    guild_id: int
    user_id: int
    level: int
    count: int
    target: int
    cached: bool = True


class DataManager(DatabaseManager):
    def __init__(self, cog: LevelCog):
        self.cog = cog
        self.pool = self.cog.bot.pool
        self.caches: Cacher[int, dict[int, LevelData]] = self.cog.bot.cachers.acquire(
            3600.0, dict
        )
        self.reward_caches: Cacher[int, dict[int, int | None]] = self.cog.bot.cachers.acquire(
            1800.0, dict
        )

    async def preapre_table(self) -> None:
        "テーブルを準備します。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS Level (
                GuildId BIGINT, UserId BIGINT, Level INTEGER,
                MessageCount INTEGER, Target INTEGER
            );"""
        )
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS LevelReward (
                GuildId BIGINT, Level INTEGER PRIMARY KEY NOT NULL,
                RoleId BIGINT
            );"""
        )

    async def _read(self, guild_id: int, user_id: int, **_) -> tuple | None:
        await cursor.execute(
            """SELECT * FROM Level
                WHERE GuildId = %s AND UserId = %s LIMIT 1;""",
            (guild_id, user_id)
        )
        if row := await cursor.fetchone():
            return row

    async def read(self, guild_id: int, user_id: int, cache: bool = True, **_) \
            -> tuple[LevelData, bool]:
        "レベルを読み込みます。"
        new = True
        if not cache or (guild_id not in self.caches or user_id not in self.caches[guild_id]):
            if (row := await self._read(guild_id, user_id, cursor=cursor)):
                self.caches[guild_id][user_id] = LevelData(*row)
                new = False
            else:
                self.caches[guild_id][user_id] = LevelData(guild_id, user_id, 0, 0, 1)
                new = True
        return self.caches[guild_id][user_id], new

    async def write(self, guild_id: int, user_id: int, **_) -> None:
        "レベルを書き込みます。"
        level, new = await self.read(guild_id, user_id, False, cursor=cursor)
        if new:
            await cursor.execute(
                "INSERT INTO Level VALUES (%s, %s, %s, %s, %s);",
                (guild_id, user_id, level.level, level.count, level.target)
            )
        else:
            await cursor.execute(
                """UPDATE Level SET Level = %s, MessageCount = %s, Target = %s
                    WHERE GuildId = %s AND UserId = %s;""",
                (level.level, level.count, level.target, guild_id, user_id)
            )

    async def read_ranking(self, guild_id: int, **_) -> list[LevelData]:
        "レベルのランキングを表示します。"
        await cursor.execute(
            "SELECT * FROM Level WHERE GuildId = %s ORDER BY Level DESC LIMIT 10;",
            (guild_id,)
        )
        return list(map(lambda x: LevelData(*x), await cursor.fetchall()))

    async def set_reward(self, guild_id: int, level: int, role_id: int | None):
        "レベル報酬を設定します。"
        if role_id is None:
            await cursor.execute(
                "DELETE FROM LevelReward WHERE GuildId = %s AND Level = %s LIMIT 1;",
                (guild_id, level)
            )
        else:
            await cursor.execute(
                """INSERT INTO LevelReward VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE RoleId = %s;""",
                (guild_id, level, role_id, role_id)
            )
        if guild_id in self.reward_caches and level in self.reward_caches[guild_id]:
            self.reward_caches[guild_id][level] = role_id

    async def read_reward(self, guild_id: int, level: int) -> int | None:
        "レベル報酬を取得します。"
        await cursor.execute(
            "SELECT RoleId FROM LevelReward WHERE GuildId = %s AND Level = %s LIMIT 1;",
            (guild_id, level)
        )
        self.reward_caches[guild_id][level] = row[0] \
            if (row := await cursor.fetchone()) else None
        return self.reward_caches[guild_id][level]

    async def read_rewards(self, guild_id: int) -> dict[int, int]:
        "レベル報酬を全て取得します。"
        await cursor.execute(
            "SELECT Level, RoleId FROM LevelReward WHERE GuildId = %s;",
            (guild_id,)
        )
        self.reward_caches[guild_id].update(data := {
            level: role_id for level, role_id in await cursor.fetchall()
        })
        return data

    async def clean(self) -> None:
        "セーブデータのお掃除をします。"
        guild, did = None, []
        async for row in self.fetchstep(cursor, "SELECT * FROM Level;"):
            if row[0] in did or row[1] in did:
                continue
            if guild is None:
                guild = self.cog.bot.get_guild(row[0])
                if guild is None and not await self.cog.bot.exists("guild", row[0]):
                    did.append(row[0])
                    if row[0] in self.caches:
                        del self.caches[row[0]]
                    await cursor.execute("DELETE FROM Level WHERE GuildId = %s;", (row[0],))
                    continue
            if not await self.cog.bot.exists("user", row[1]):
                await cursor.execute("DELETE FROM Level WHERE UserId = %s;", (row[1],))
            did.append(row[1])
        await self.cog.bot.clean(cursor, "LevelReward", "GuildId")


class LevelRewardEventContext(Cog.EventContext):
    message: discord.Message
    level: LevelData
    role: discord.Role


class LevelCog(Cog, name="Level"):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)
        self.queues: list[discord.Member] = []

    async def cog_load(self):
        await self.data.preapre_table()
        self.process_queues.start()

    async def cog_unload(self):
        self.process_queues.cancel()

    @commands.group(
        aliases=("lv", "レベル"), fsparent=FSPARENT,
        description="Level, and level reward"
    )
    async def level(self, ctx: commands.Context):
        await self.group_index(ctx)

    (_LEVEL_HELP := Cog.HelpCommand(level)
        .merge_headline(ja="レベル、レベル報酬")
        .set_description(
            ja="""レベルとレベル報酬です。
            レベルというのは喋れば喋るほど上がっていく数字のことです。
            誰がどれだけ喋っているかを確認することができます。
            また、特定のレベルに達した際にロールを付与するように設定することもできます。""",
            en="""Levels and Level Rewards.
            Level is a number that goes up the more you talk.
            You can see who is talking and how much they are talking.
            It can also be set up to add role upon reaching a certain level."""
        ))

    @level.command("set", aliases=SET_ALIASES, description="Set user level.")
    @commands.has_guild_permissions(administrator=True)
    @commands.cooldown(1, 15, commands.BucketType.guild)
    @discord.app_commands.describe(level="The new level", user="Target member")
    async def set_level(
        self, ctx: commands.Context, level: int, *,
        user: discord.Member | None = None
    ):
        if 0 > level or level >= 23170:
            raise Cog.reply_error.BadRequest(TOO_SMALL_OR_LARGE_NUMBER)
        await ctx.typing()
        assert ctx.guild is not None and isinstance(ctx.author, discord.Member)
        user = user or ctx.author
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                now, _ = await self.data.read(ctx.guild.id, user.id, cursor=cursor)
                now.level = level
                now.target = level + 1
                now.count = 0
                await self.data.write(ctx.guild.id, user.id, cursor=cursor)
        await ctx.reply("Ok")

    _LEVEL_HELP.add_sub(Cog.HelpCommand(set_level)
        .set_description(ja="ユーザーのレベルを設定します。", en=set_level.description)
        .add_arg("level", "int",
            ja="設定するレベルです。", en="The level to be set.")
        .add_arg("user", "Member", "Optional",
            ja="""設定する対象のメンバーです。
                指定されなかった場合はコマンドの実行者が対象となります。""",
            en="""The target member to set.
                If not specified, the executor of the command is targeted."""))

    @level.command("show", aliases=SHOW_ALIASES, description="Displays user level.")
    @discord.app_commands.describe(user="Target member")
    async def show_level(self, ctx: commands.Context, *, user: discord.Member | None = None):
        await ctx.typing()
        assert ctx.guild is not None and isinstance(ctx.author, discord.Member)
        user = user or ctx.author
        data, _ = await self.data.read(ctx.guild.id, user.id)
        await ctx.reply(embed=Cog.Embed(
            t(dict(ja="{name}のレベル", en="{name}'s level"), ctx, name=user.display_name),
            description=t(dict(
                ja="レベル：{level}\n次のレベルまで：{next_}",
                en="Level: {level}\nUp to the next level: {next_}"
            ), ctx, level=data.level, next_=data.target - data.count)
        ))

    _LEVEL_HELP.add_sub(Cog.HelpCommand(show_level)
        .set_description(ja="指定したユーザーのレベルを表示します。", en=show_level.description)
        .add_arg("user", "Member", "Optional",
            ja="""表示するレベルを持っているメンバーです。
                指定しない場合はコマンドを実行した人が対象となります。""",
            en="""The member has the level to display.
                If not specified, the executor of the command is targeted."""))

    @level.command(aliases=("rank", "r", "ランキング", "順位"), description="Displays the ranking.")
    async def ranking(self, ctx: commands.Context):
        await ctx.typing()
        guild = ctx.guild
        assert guild is not None
        await ctx.reply(embed=Cog.Embed(
            t(dict(ja="レベルランキング", en="Level ranking"), ctx),
            description="\n".join(
                f"**{index}**：{member}　`{data.level}`"
                for index, (member, data) in enumerate([
                    (await self.bot.search_member(guild, data.user_id), data)
                    for data in await self.data.read_ranking(guild.id)
                ], 1)
                if member is not None
            )
        ))

    _LEVEL_HELP.add_sub(Cog.HelpCommand(ranking)
        .set_description(ja="ランキングを表示します。", en=ranking.description))

    @level.group(
        aliases=("rwd", "報酬", "リワード"),
        description="Level reward"
    )
    @commands.has_guild_permissions(manage_roles=True)
    async def reward(self, ctx: commands.Context):
        await self.group_index(ctx)

    _LEVEL_HELP.add_sub(Cog.HelpCommand(reward)
        .set_description(
            ja="""レベル報酬です。
                レベルアップ時にロールを付与することができます。""",
            en="""Level Rewards.
                Roles can be added upon leveling up.""")
        .set_extra("Notes",
            ja="`role_linker`と一緒に使うことで、報酬受け取り時に元々持っていたロールを剥奪することができます。",
            en="Used in conjunction with `role_linker`, it can be used to strip a person of the roles they originally had when they received their reward."))

    @reward.command(
        "set", aliases=SET_ALIASES,
        description="Set level reward."
    )
    @discord.app_commands.describe(
        level=(_d_l := "At what level will the reward roll be granted?"),
        role=(_d_r := "The role to be added for reward.")
    )
    async def set_reward(self, ctx: commands.Context, level: int, *, role: discord.Role):
        await ctx.typing()
        assert ctx.guild is not None
        await self.data.set_reward(ctx.guild.id, level, role.id)
        await ctx.reply("Ok")

    _LEVEL_HELP.add_sub(Cog.HelpCommand(set_reward)
        .set_description(ja="レベル報酬を設定します。", en=set_reward.description)
        .add_arg("level", "int",
            ja="どのレベルになった時に報酬のロールを付与するかです。", en=_d_l)
        .add_arg("reward", "Role", ja="報酬として渡すロールです。", en=_d_r))
    del _d_r

    @reward.command(
        "delete", aliases=DELETE_ALIASES,
        description="Delete level reward."
    )
    @discord.app_commands.describe(level=_d_l)
    async def delete_reward(self, ctx: commands.Context, *, level: int):
        await ctx.typing()
        assert ctx.guild is not None
        await self.data.set_reward(ctx.guild.id, level, None)
        await ctx.reply("Ok")

    _LEVEL_HELP.add_sub(Cog.HelpCommand(delete_reward)
        .set_description(ja="レベル報酬を削除します。", en=delete_reward.description)
        .add_arg("level", "int",
            ja="削除する報酬に設定されているレベルです。",
            en="This is the level set for the reward to be deleted."))

    @reward.command(
        "list", aliases=LIST_ALIASES,
        description="Displays the setting of level reward."
    )
    async def list_reward(self, ctx: commands.Context):
        await ctx.typing()
        assert ctx.guild is not None
        await ctx.reply(embed=Cog.Embed("LevelReward", description="\n".join(
            f"・{level}：<@&{role_id}>"
            for level, role_id in (await self.data.read_rewards(ctx.guild.id)).items()
        )))

    _LEVEL_HELP.add_sub(Cog.HelpCommand(list_reward)
        .set_description(ja="設定されているレベル報酬を表示します。", en=list_reward.description))
    del _d_l, _LEVEL_HELP

    @tasks.loop(seconds=15)
    async def process_queues(self):
        for member in self.queues:
            if isinstance(member, discord.Member):
                await self.data.write(member.guild.id, member.id)
        self.queues = []

    async def process_reward(self, message: discord.Message, level: LevelData) -> None:
        assert message.guild is not None
        if (role_id := await self.data.read_reward(message.guild.id, level.level)) is not None:
            detail = ""
            if (role := message.guild.get_role(role_id)) is None:
                detail = ROLE_NOTFOUND
            else:
                assert isinstance(message.author, discord.Member)
                try:
                    await message.author.add_roles(role, reason="Level Reward / レベル報酬")
                except discord.Forbidden:
                    detail = FORBIDDEN
            self.bot.rtevent.dispatch("on_level_reward", LevelRewardEventContext(
                self.bot, message.guild, "ERROR" if detail else "SUCCESS",
                {"ja": "レベル報酬の付与", "en": "Add lrevel reward role"},
                detail, self.level
            ))

    @commands.Cog.listener()
    async def on_message_noprefix(self, message: discord.Message):
        if message.guild is None or not isinstance(message.author, discord.Member):
            return

        level, _ = await self.data.read(message.guild.id, message.author.id)
        # レベル用のメッセージ数を加算する。
        level.count += 1
        if level.level < 23170:
            if level.count == level.target:
                # レベルアップさせる。
                level.level += 1
                level.target = calculate(level.level + 1)
                level.count = 0
                await self.process_reward(message, level)
        # レベルのセーブキューにメンバーを追加する。
        if message.author not in self.queues:
            self.queues.append(message.author)


async def setup(bot: RT) -> None:
    await bot.add_cog(LevelCog(bot))