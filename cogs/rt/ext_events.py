# RT - Ext Events

from typing import Literal

from dataclasses import dataclass

from discord.ext import commands
import discord

from core import Cog, RT

from rtlib.common.cacher import Cacher


@dataclass
class Caches:
    members: Cacher[tuple[int, int], int]


class ExtEvents(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.caches = Caches(
            self.bot.cachers.acquire(30.0)
        )

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # メンバーのロールの付与と削除のイベントを呼び出します。
        for role in after.roles:
            if not role.is_default() and before.get_role(role.id) is None:
                self.bot.dispatch("member_role_add", after, role)
        for role in before.roles:
            if not role.is_default() and after.get_role(role.id) is None:
                self.bot.dispatch("member_role_remove", after, role)

    def on_member(self, mode: Literal["join", "remove"], member: discord.Member):
        if (now := self.caches.members.get((member.guild.id, member.id), 0)) < 3:
            self.caches.members[(member.guild.id, member.id)] = now + 1
            self.bot.dispatch(f"member_{mode}_cooldown", member)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        self.on_member("join", member)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        self.on_member("remove", member)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.data is not None and "custom_id" in interaction.data:
            self.bot.dispatch("interaction_custom_id", interaction)


async def setup(bot: RT) -> None:
    await bot.add_cog(ExtEvents(bot))