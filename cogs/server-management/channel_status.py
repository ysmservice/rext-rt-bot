# RT - Channel Status

from discord.ext import commands
import discord

from core import Cog, RT, t

from data import SET_ALIASES, DELETE_ALIASES, LIST_ALIASES, FORBIDDEN, CHANNEL_NOTFOUND

from .__init__ import FSPARENT


class ChannelStatus(Cog):
    def __init__(self, bot: RT):
        self.bot = bot

    @commands.group(
        aliases=("ch_stats", "csts", "チャンネルステータス", "ちす"), fsparent=FSPARENT,
        description="Displays information about the server on the channel."
    )
    async def channel_status(self, ctx: commands.Context):
        await self.group_index(ctx)

    @channel_status.command(
        "set", aliases=SET_ALIASES,
        description="Set the status of the server to the channel."
    )
    async def set_(self, ctx: commands.Context):
        ...

    @channel_status.command(aliases=DELETE_ALIASES, description="Delete the setting of the status.")
    async def delete(self, ctx: commands.Context):
        ...

    @channel_status.command("list", aliases=LIST_ALIASES, description="Displays list of settings.")
    async def list_(self, ctx: commands.Context):
        ...


async def setup(bot: RT) -> None:
    await bot.add_cog(ChannelStatus(bot))