# RT - Ext Events

from discord.ext import commands
import discord

from core import Cog, RT


class ExtEvents(Cog):
    def __init__(self, bot: RT):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # メンバーのロールの付与と削除のイベントを呼び出します。
        for role in after.roles:
            if not role.is_default() and before.get_role(role.id) is None:
                self.bot.dispatch("member_role_add", after, role)
        for role in before.roles:
            if not role.is_default() and after.get_role(role.id) is None:
                self.bot.dispatch("member_role_remove", after, role)


async def setup(bot: RT) -> None:
    await bot.add_cog(ExtEvents(bot))