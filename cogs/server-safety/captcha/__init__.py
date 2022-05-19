# RT - Captcha

from __future__ import annotations

from typing import Literal, Any, overload

from dataclasses import dataclass
from asyncio import create_task
from time import time

from discord.ext import commands
import discord

from orjson import dumps, loads

from core import RT, Cog, t, DatabaseManager, cursor

from rtlib.common.cacher import Cacher

from data import OFF_ALIASES

from .part import CaptchaContext, CaptchaPart, CaptchaView, RowData, Mode
from .oneclick import OneClickCaptchaPart
from .web import WebCaptchaPart
from .word import WordCaptchaPart
from .image import ImageCaptchaPart


class DataManager(DatabaseManager):
    def __init__(self, cog: Captcha):
        self.cog = cog
        self.pool = self.cog.bot.pool
        self.caches: Cacher[int, RowData | None] = self.cog.bot.cachers.acquire(1800.0)

    async def prepare_table(self) -> None:
        "テーブルを作ります。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS Captcha (
                GuildId BIGINT PRIMARY KEY NOT NULL, RoleId BIGINT,
                Mode ENUM("image", "word", "web", "oneclick"),
                DeadlineAfter FLOAT, Kick BOOLEAN, Extras JSON
            );"""
        )

    async def write_deadline(self, guild_id: int, deadline: float, kick: bool) -> None:
        "期限を設定します。"
        await cursor.execute(
            "UPDATE Captcha SET DeadlineAfter = %s, Kick = %s WHERE GuildId = %s;",
            (deadline, kick, guild_id)
        )

    async def write(
        self, guild_id: int, role_id: int,
        mode: Mode, extras: dict[str, Any]
    ) -> None:
        "設定を書き込みます。"
        row = (guild_id, role_id, mode, 3600.0, True, dumps(extras).decode())
        await cursor.execute(
            """INSERT INTO Captcha VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE RoleId = %s, Mode = %s;""",
            row + row[1:-3]
        )
        if guild_id in self.caches:
            self.caches[guild_id] = RowData(*row[:-1], extras)

    async def delete(self, guild_id: int) -> None:
        "設定を削除します。"
        await cursor.execute(
            "DELETE FROM Captcha WHERE GuildId = %s;",
            (guild_id,)
        )
        if guild_id in self.caches:
            self.caches[guild_id] = None

    async def read(self, guild_id: int) -> RowData | None:
        "設定を読み込みます。"
        if guild_id not in self.caches:
            await cursor.execute(
                "SELECT * FROM Captcha WHERE GuildId = %s;",
                (guild_id,)
            )
            if row := await cursor.fetchone():
                self.caches[guild_id] = RowData(*row[:-1], loads(row[-1])) # type: ignore
        return self.caches[guild_id]


@dataclass
class Parts:
    "認証のパーツを格納するためのクラスです。"

    word: WordCaptchaPart
    web: WebCaptchaPart
    oneclick: OneClickCaptchaPart
    image: ImageCaptchaPart


class Captcha(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.queues: Cacher[discord.Member, CaptchaContext] = self.bot.cachers.acquire(
            10800.0, on_dead=self.on_dead_queue
        )
        self.parts = Parts(*(globals()[name](self) for name in Parts.__annotations__.values()))
        self.data = DataManager(self)
        if not getattr(self.bot, "_captcha_patched", False):
            self.view = CaptchaView(self)
            self.bot.add_view(self.view)
            setattr(self.bot, "_captcha_patched", True)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.Cog.listener()
    async def on_setup(self):
        self.bot.ipcs.set_route(self.parts.web.on_success)

    def on_dead_queue(self, _, ctx: CaptchaContext) -> None:
        "キューが削除された際に呼ばれる関数です。"
        create_task(ctx.part.on_queue_remove(ctx))
        create_task(self.after_captcha(ctx))

    async def after_captcha(self, ctx: CaptchaContext) -> None:
        "キューが消された後の後処理をする。(キック等)\n`.on_dead_queue`から呼ばれる。"
        ctx.event_context.log = False
        if not ctx.success:
            if ctx.data.kick:
                ctx.event_context.detail = t(dict(
                    ja="認証期限が切れたのでキックをしようとした。",
                    en="Attempted to kick the certification because it had expired."
                ), ctx.member.guild)
                try:
                    await ctx.member.kick(reason=t(dict(
                        ja="認証期限が過ぎたため。", en="Because the certification deadline has passed."
                    ), ctx.member.guild))
                except discord.Forbidden:
                    ctx.event_context.detail = "{}\n{}".format(
                        ctx.event_context.detail, t(self.FORBIDDEN, ctx.member.guild)
                    )
                else:
                    ctx.event_context.status = "SUCCESS"
                ctx.event_context.log = True
        self.bot.rtevent.dispatch("on_captcha_end", ctx.event_context)

    def get_part(self, type_: str) -> CaptchaPart:
        "CaptchaPartを手に入れます。"
        return getattr(self.parts, type_)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        data = await self.data.read(member.guild.id)
        if data is not None:
            self.queues[member] = CaptchaContext(
                data=data, part=self.get_part(data.mode), member=member,
                event_context=Cog.EventContext(
                    self.bot, member.guild, "ERROR", {
                        "ja": "認証成功時のロール付与",
                        "en": "Granting roles upon successful authentication"
                    }, feature=self.captcha
                )
            )
            self.queues.set_deadline(member, time() + data.deadline)

    @overload
    async def on_success(
        self, ctx: CaptchaContext, interaction: None,
        mode: Literal["edit", "send"] = "edit", **kwargs
    ) -> str: ...
    @overload
    async def on_success(
        self, ctx: CaptchaContext, interaction: discord.Interaction,
        mode: Literal["edit", "send"] = "edit", **kwargs
    ) -> None: ...
    async def on_success(
        self, ctx: CaptchaContext, interaction: discord.Interaction | None,
        mode: Literal["edit", "send"] = "edit", **kwargs
    ) -> None | str:
        "認証成功時に呼ばれるべき関数です。ロールを付与します。"
        ctx.success = True
        del self.queues[ctx.member]

        # ロールを用意する。
        if (role := ctx.member.guild.get_role(ctx.data.role_id)) is None:
            ctx.event_context.detail += "\n{}".format(t(
                self.NOTFOUND("ロール", "Role"), ctx.member.guild
            ))
            kwargs["content"] = t(dict(
                ja="認証は成功しましたが、付与する役職が見つかりませんでした。",
                en="Captcha succeeded, but the role to be granted was not found."
            ), interaction)
        else:
            # ロールを付与する。
            try:
                await ctx.member.add_roles(role)
            except discord.Forbidden:
                ctx.event_context.detail += "\n{}".format(t(
                    self.FORBIDDEN, ctx.member.guild
                ))
                kwargs["content"] = t(dict(
                    ja="認証は成功しましたが、権限がないため役職の付与に失敗しました。",
                    en="Captcha succeeded, but failed to grant the role due to lack of permission."
                ), interaction)
            else:
                ctx.event_context.status = "SUCCESS"
                kwargs["content"] = t(dict(
                    ja="認証に成功しました。", en="Captcha succeeded."
                ), interaction)

        self.bot.rtevent.dispatch("on_captcha_success", ctx.event_context)

        if interaction is None:
            return kwargs["content"]
        else:
            if mode == "send":
                kwargs.setdefault("ephemeral")
                await interaction.response.send_message(**kwargs)
            else:
                kwargs.setdefault("view", None)
                await interaction.response.edit_message(**kwargs)

    @commands.group(
        aliases=("認証", "authentication", "auth"),
        description="Set up captcha"
    )
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def captcha(self, ctx: commands.Context):
        await self.group_index(ctx)

    async def setup(
        self, ctx: commands.Context, mode: Mode, role: discord.Role,
        extras: dict[str, Any] | None = None
    ) -> None:
        async with ctx.typing():
            assert ctx.guild is not None
            await self.data.write(ctx.guild.id, role.id, mode, extras or {})
        await ctx.channel.send(content=t(dict(
            ja="以下のボタンから認証を行なってください。",
            en="Please click the button below to authenticate."
        ), ctx.guild), view=self.view)

    @captcha.command(aliases=("画像", "img"), description="Set up image captcha")
    async def image(self, ctx: commands.Context, *, role: discord.Role):
        await self.setup(ctx, "image", role)

    @captcha.command(aliases=("合言葉",), description="Set up word captcha")
    async def word(
        self, ctx: commands.Context, word: str,
        mode: Literal["partial", "full"], *,
        role: discord.Role
    ):
        await self.setup(ctx, "word", role, {"word": word, "mode": mode})

    @captcha.command(aliases=("ウェブ",), description="Set up web captcha")
    async def web(self, ctx: commands.Context, *, role: discord.Role):
        await self.setup(ctx, "web", role)

    @captcha.command(aliases=("ワンクリック", "oc"), description="Set up web captcha")
    async def oneclick(self, ctx: commands.Context, *, role: discord.Role):
        await self.setup(ctx, "oneclick", role)

    @captcha.command(
        aliases=("dl", "timeout", "to", "期限", "タイムアウト"),
        description="Sets the deadline for the captcha."
    )
    async def deadline(self, ctx: commands.Context, deadline: float, kick: bool):
        async with ctx.typing():
            assert ctx.guild is not None
            await self.data.write_deadline(ctx.guild.id, deadline, kick)
        await ctx.reply("Ok")

    @captcha.command(
        aliases=OFF_ALIASES, description="Remove the captcha setting."
    )
    async def off(self, ctx: commands.Context):
        async with ctx.typing():
            assert ctx.guild is not None
            await self.data.delete(ctx.guild.id)
        await ctx.reply("Ok")


async def setup(bot):
    await bot.add_cog(Captcha(bot))