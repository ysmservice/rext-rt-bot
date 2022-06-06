# RT - Server Tool

from __future__ import annotations

from collections.abc import AsyncIterator

from time import time

from discord.ext import commands, tasks
import discord

from core import Cog, RT, t, DatabaseManager, cursor

from data import EMOJIS, PERMISSION_TEXTS, NOTFOUND, NO_MORE_SETTING, CHANNEL_NOTFOUND, FORBIDDEN


FSPARENT = "server-tool"


class DataManager(DatabaseManager):
    def __init__(self, cog: ServerTool):
        self.cog = cog
        self.pool = self.cog.bot.pool

    async def prepare_table(self) -> None:
        "テーブルを作ります。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS UnLockQueues (
                GuildId BIGINT, ChannelId BIGINT PRIMARY KEY NOT NULL,
                Time DOUBLE
            );"""
        )

    async def read_all_unlock_queues(self, **_) -> AsyncIterator[tuple[int, int, float]]:
        "アンロックキューを全て取得します。"
        async for row in self.fetchstep(cursor, "SELECT * FROM UnLockQueues;"):
            yield row

    async def read_unlock_queues(self, guild_id: int, **_) -> dict[int, float]:
        "アンロックキューを取得します。"
        await cursor.execute(
            "SELECT ChannelId, Time FROM UnLockQueues WHERE GuildId = %s;",
            (guild_id,)
        )
        return {row[0]: row[1] for row in await cursor.fetchall()}
    
    async def read_unlock_queue(self, channel_id: int, **_) -> float | None:
        "アンロックキューを取得します。"
        await cursor.execute(
            "SELECT Time FROM UnLockQueues WHERE ChannelId = %s;",
            (channel_id,)
        )
        if row := await cursor.fetchone():
            return row[0]

    async def add_unlock_queue(self, guild_id: int, channel_id: int, time_: float) -> None:
        "アンロックキューを追加する。"
        data = await self.read_unlock_queues(guild_id, cursor=cursor)
        if len(data) > 10:
            raise Cog.BadRequest(NO_MORE_SETTING)
        await cursor.execute(
            """INSERT INTO UnLockQueues VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE Time = %s;""",
            (guild_id, channel_id, time_, time_)
        )

    async def remove_unlock_queues(self, channel_id: int, **_) -> None:
        "アンロックキューを削除します。"
        await cursor.execute(
            "DELETE FROM UnLockQueues WHERE ChannelId = %s;",
            (channel_id,)
        )

    async def clean(self) -> None:
        "データの掃除をします。"
        await self.clean_data(cursor, "UnLockQueues", "ChannelId")


class LockEventContext(Cog.EventContext):
    "チャンネルのロックまたは解除のイベントコンテキストです。"

    channel: discord.TextChannel | discord.VoiceChannel | None


class ServerTool(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)

    async def cog_load(self) -> None:
        await self.data.prepare_table()
        self._auto_unlock.start()

    async def cog_unload(self) -> None:
        self._auto_unlock.cancel()

    @tasks.loop(seconds=30)
    async def _auto_unlock(self):
        # アンロックキューのチャンネルのロックを解除する。
        guild, now = None, time()
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                async for row in self.data.read_all_unlock_queues(cursor=cursor):
                    if guild is None or guild.id != row[0]:
                        guild = self.bot.get_guild(row[0])
                    if guild is None:
                        continue

                    remove, error = False, None
                    if (channel := guild.get_channel(row[1])) is None:
                        remove = True
                        error = CHANNEL_NOTFOUND
                    if not remove and now > row[2]:
                        remove = True
                        assert isinstance(channel, discord.TextChannel | discord.VoiceChannel)
                        # ロックを行う。
                        try:
                            await self._lockman_core(channel, True)
                        except discord.Forbidden:
                            error = FORBIDDEN
                    if remove:
                        await self.data.remove_unlock_queues(row[1], cursor=cursor)

                    self.bot.rtevent.dispatch("on_lock_channel", LockEventContext(
                        self.bot, guild, self.detail_or(error), {
                            "ja": "自動アンロック", "en": "Auto unlock"
                        }, self.text_format(
                            {"ja": "チャンネル：{ch}", "en": "Channel: {ch}"},
                            ch=row[1] if channel is None else self.name_and_id(channel)
                        ), self.lock, error
                    ))

    @_auto_unlock.before_loop
    async def _before_auto_unlock(self):
        await self.bot.wait_until_ready()

    def _get_lock_mode(self, lock: bool) -> dict[str, str]:
        # ロックのモードの文字列を取得します。
        return dict(ja="ロック", en="Lock") \
            if lock else dict(ja="アンロック", en="Un lock")

    async def _lockman_core(
        self, channel: discord.TextChannel | discord.VoiceChannel,
        unlock: bool
    ) -> set[discord.Role | discord.Member]:
        # ロックまたはロックの解除をします。
        targets = set()
        if not channel.overwrites:
            targets.add(channel.guild.default_role)
            await channel.edit(overwrites={
                channel.guild.default_role: discord.PermissionOverwrite( # type: ignore
                    send_messages=unlock
                )
            })

        length = len(channel.overwrites)
        for obj in channel.overwrites:
            if length != 1 and obj.name == "@everyone":
                continue
            overwrites = channel.overwrites_for(obj)
            overwrites.send_messages = unlock
            targets.add(obj)
            await channel.set_permissions(
                obj, overwrite=overwrites, reason=t(self._get_lock_mode(
                    not unlock
                ), channel.guild)
            )

        return targets

    async def _lockman(
        self, ctx: commands.Context,
        channel: discord.TextChannel | discord.VoiceChannel | None,
        lock: bool, auto_unlock: bool = False
    ) -> None:
        # `._lockman_core`を実行した後に返信を行います。
        if isinstance(ctx.channel, discord.TextChannel):
            await ctx.typing()
            assert ctx.guild is not None
            await ctx.reply(t(dict(
                ja="※自動アンロックが有効です。", en="* I will unlock this channel."
            ), ctx) if auto_unlock else None, embed=Cog.Embed(
                t(self._get_lock_mode(lock), ctx), description=", ".join(
                    obj.mention for obj in await self._lockman_core(
                        (channel or ctx.channel), not lock
                    )
                )
            ))
        else:
            await ctx.reply(t(dict(
                ja="テキストチャンネルでしかこのコマンドは実行できません。",
                en="You can only execute this command on a text channel."
            ), ctx))

    @commands.command(
        aliases=("l", "ロック", "マン", "ろ"), fsparent=FSPARENT,
        description="Make the channel unable to speak without permission."
    )
    @discord.app_commands.describe(
        after=(_a_d := "The value of how many minutes later to automatically unlock."),
        channel=(_c_d := "Target channel. If not specified, the channel where the command was executed is the target.")
    )
    @commands.cooldown(1, 600, commands.BucketType.guild)
    @commands.has_guild_permissions(manage_channels=True, manage_roles=True)
    async def lock(
        self, ctx: commands.Context, after: float | None = None, *,
        channel: discord.TextChannel | discord.VoiceChannel | None = None
    ):
        if after is not None:
            async with ctx.typing():
                assert ctx.guild is not None
                await self.data.add_unlock_queue(
                    ctx.guild.id, ctx.channel.id,
                    time() + 60 * after
                )
        await self._lockman(ctx, channel, True, after is not None)

    @commands.command(
        aliases=("ul", "アンロック", "あろ"), fsparent=False,
        description="Unlock the channel."
    )
    @discord.app_commands.describe(channel=_c_d)
    @commands.cooldown(1, 600, commands.BucketType.guild)
    @commands.has_guild_permissions(manage_channels=True, manage_roles=True)
    async def unlock(
        self, ctx: commands.Context, *,
        channel: discord.TextChannel | discord.VoiceChannel | None = None
    ):
        await self._lockman(ctx, channel, False)

    (Cog.HelpCommand(lock)
        .merge_description("headline", ja="チャンネルを権限がないと喋れないようにします。")
        .add_arg("after", "float", "Optional",
            ja="何分後に自動にロックを解除するかです。", en=_a_d)
        .add_arg("channel", "Channel", "Optional",
            ja=(_c_d_ja := "対象のチャンネルです。指定されない場合はコマンドを実行したチャンネルが使われます。"),
            en=_c_d)
        .set_extra("See Also",
            ja="`unlock` チャンネルのロックを解除します。",
            en="`unlock` Unlock the channel."))
    (Cog.HelpCommand(unlock)
        .merge_description("headline", ja="チャンネルのロックを解除します。")
        .add_arg("channel", "Channel", "Optional", ja=_c_d_ja, en=_c_d)
        .set_extra("See Also",
            ja="`lock` チャンネルをロックします。",
            en="`lock` Lock the channel."))
    del _a_d, _c_d, _c_d_ja

    @commands.command(
        aliases=("invs", "招待ランキング"), fsparent=FSPARENT,
        description="Invitation ranking is displayed."
    )
    async def invites(self, ctx: commands.Context):
        assert ctx.guild is not None
        await ctx.reply(embed=Cog.Embed(
            title=t(dict(
                ja="{guild_name}の招待ランキング",
                en="Invitation ranking of {guild_name}"
            ), ctx, guild_name=ctx.guild.name), description='\n'.join(
                f"{a}：`{c}`" for a, c in sorted((
                    (f"{i.inviter.mention}({i.code})", i.uses or 0)
                    for i in await ctx.guild.invites()
                    if i.inviter is not None and i.uses
                ), reverse=True, key=lambda x: x[1])
            )
        ))

    (Cog.HelpCommand(invites)
        .merge_headline(ja="招待ランキング")
        .set_description(ja="招待ランキングを表示します。", en=invites.description))

    @commands.command(
        aliases=("perms", "権限", "戦闘力"), fsparent=FSPARENT,
        description="Displays the permissions held by the specified member."
    )
    async def permissions(self, ctx: commands.Context, *, member: discord.Member | None = None):
        member = member or ctx.guild.default_role # type: ignore
        permissions = getattr(member, "guild_permissions", getattr(
            member, "permissions", None
        ))

        if permissions is None:
            await ctx.reply(t(dict(
                ja="見つかりませんでした。", en="Not found..."
            ), ctx))
        else:
            await ctx.reply(embed=Cog.Embed(
                title=t(
                    {"ja": "{name}の権限一覧", "en": "{name}'s Permissions"},
                    ctx, name=member.name # type: ignore
                ),
                description="\n".join(
                    f"{EMOJIS['success']} {t(PERMISSION_TEXTS[name], ctx)}"
                        if getattr(permissions, name, False)
                        else f"{EMOJIS['error']} {t(PERMISSION_TEXTS[name], ctx)}"
                    for name in PERMISSION_TEXTS
                )
            ))

    (Cog.HelpCommand(permissions)
        .merge_headline(ja="指定したユーザーが所有している権限を表示します。")
        .set_description(ja="指定したユーザーが所有している権限を表示します。", en=permissions.description)
        .add_arg("member", "Member", "Optional",
            ja="""所有している権限を見たい対象のメンバーです。
                指定しない場合は`@everyone`ロール(全員が持っている権限)となります。""",
            en="""The members of the target group who want to see the privileges they possess.
                If not specified, it will be the `@everyone` role (the authority that everyone has)."""))

    @commands.command(
        fsparent=FSPARENT, aliases=("si", "サーバー情報"),
        description="Show server information."
    )
    @discord.app_commands.describe(target="The id of server.")
    async def serverinfo(self, ctx, *, target: int | None = None):
        guild = ctx.guild if target is None else await self.bot.search_guild(target)
        if guild is None:
            raise Cog.BadRequest(NOTFOUND)
        embed = Cog.Embed(title=t({"ja": "{name}の情報","en": "{name}'s information"}, ctx, name=guild.name))
        embed.add_field(
            name=t({"ja": "サーバー名", "en": "Server name"}, ctx),
            value=f"{guild.name} (`{guild.id}`)"
        )
        embed.add_field(
            name=t({"ja": "サーバー作成日時", "en": "Server created at"}, ctx),
            value=f"<t:{int(guild.created_at.timestamp())}>"
        )
        if guild.owner is not None:
            embed.add_field(
                name=t({"ja": "サーバーの作成者", "en": "Server owner"}, ctx),
                value=f"{guild.owner} (`{guild.owner.id}`)"
            )
        if guild.member_count is not None:
            embed.add_field(
                name=t({"ja": "サーバーのメンバー数", "en": "Server member count"}, ctx),
                value="{} ({})".format(guild.member_count, guild.member_count - len(
                    set(filter(lambda m: m.bot, guild.members))
                ))
            )
        text, voice, count = 0, 0, 0
        for count, channel in enumerate(guild.channels, 1):
            if isinstance(channel, discord.TextChannel | discord.Thread):
                text += 1
            else:
                voice += 1
        embed.add_field(
            name=t({"ja": "サーバーのチャンネル数", "en": "Server channel count"}, ctx),
            value=t(dict(
                ja="`{sum_}` (テキストチャンネル：`{text_}`, ボイスチャンネル：`{voice}`)",
                en="`{sum_}` (Text channels: `{text_}`, Voice channels: `{voice}`)"
            ), ctx, sum_=count, text_=text, voice=voice)
        )
        await ctx.reply(embed=embed)

    (Cog.HelpCommand(serverinfo)
        .set_headline(ja="サーバーを検索します。")
        .add_arg("target", "int", "Optional",
            ja="サーバーのIDです。", en="Server's id.")
        .set_description(ja="サーバーを検索します", en="Search server"))


async def setup(bot: RT) -> None:
    await bot.add_cog(ServerTool(bot))