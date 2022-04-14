# RT - General

from inspect import cleandoc

from discord.ext import commands, tasks
import discord

from rtlib import RT, Cog, Embed, t


RT_INFO = {
    "ja": cleandoc(
        """どうも、Rextが運営している有料のBotであるRTです。
        多機能で安定した高品質なBotを目指しています。
        詳細は[ここ](https://rt.rext.dev)をご覧ください。"""
    ), "en": cleandoc(
        """Hi, this is RT, a paid bot operated by Rext.
        We aim to be a multifunctional, stable and high quality bot.
        For more information, please visit [here](https://rt.rext.dev)."""
    )
}


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
        aliases=("p", "latency", "レイテンシ"),
        description="Displays RT's latency."
    )
    async def ping(self, ctx: commands.Context):
        await ctx.reply(embed=Embed(
            title=t(dict(ja="RTのレイテンシ", en="RT Latency"), ctx)
        ).add_field(name="Bot", value=self.bot.parsed_latency))

    Cog.HelpCommand(ping) \
        .set_description(
            ja="現在のRTの通信状況を表示します。", en="Displays latency of RT."
        ) \
        .set_extra(
            "Notes", ja="200msを超えている場合は通信が遅いです。",
            en="If it exceeds 200 ms, communication is slow."
        ) \
        .update_headline(ja="RTのレイテンシを表示します。a")

    async def cog_unload(self):
        self.status_updater.cancel()

    @commands.command(description="Displays info of RT.")
    async def info(self, ctx: commands.Context):
        await ctx.reply(embed=Cog.Embed("RT Info", description=t(RT_INFO, ctx)))

    Cog.HelpCommand(info) \
        .set_description(ja="RTの情報を表示します。", en="Displays info of RT.") \
        .update_headline(ja="RTの情報を表示します。")


async def setup(bot):
    await bot.add_cog(General(bot))