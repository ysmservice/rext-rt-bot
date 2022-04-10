# RT - General

from discord.ext import commands, tasks
import discord

from rtlib import RT, Cog, Embed, t


class General(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.status_modes = ("guilds", "users")
        self.now_status_mode = "guilds"
        self.status_updater.start()

    @tasks.loop(minutes=1)
    async def status_updater(self):
        # Update status
        await self.bot.change_presence(
            activity=discord.Activity(
                name=f"/help | {len(getattr(self.bot, self.now_status_mode))} {self.now_status_mode}",
                type=discord.ActivityType.watching
            )
        )
        for mode in self.status_modes:
            if mode != self.status_modes:
                self.now_status_mode = mode

    @commands.command(
        aliases=("p", "latency", "レイテンシ"), category="rt",
        description="Displays RT's latency."
    )
    async def ping(self, ctx: commands.Context):
        await ctx.reply(embed=Embed(
            title=t(dict(ja="RTのレイテンシ", en="RT Latency"), ctx)
        ).add_field(name="Bot", value=f"{self.bot.get_parsed_latency()}ms"))

    Cog.HelpCommand(ping) \
        .set_description(
            ja="現在のRTの通信状況を表示します。", en="Displays latency of RT."
        ) \
        .set_extra(
            "Notes", ja="200msを超えている場合は通信が遅いです。",
            en="If it exceeds 200 ms, communication is slow."
        ) \
        .update_headline(ja="RTのレイテンシを表示します。")

    async def cog_unload(self):
        self.status_updater.cancel()


async def setup(bot):
    await bot.add_cog(General(bot))