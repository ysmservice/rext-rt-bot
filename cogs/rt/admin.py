# RT - Admin

from typing import Literal

from asyncio import all_tasks
from platform import system

from discord.ext import commands
import discord

from jishaku.functools import executor_function
import psutil

from core.utils import separate
from core import RT, Cog, t

from rtlib.common.utils import code_block

from rtutil.views import EmbedPage
from rtutil.utils import set_page


class Admin(Cog):
    def __init__(self, bot: RT):
        self.bot = bot

    @commands.group(aliases=("sudo", "ad", "管理", "debug"), description="Tools for administration")
    @commands.is_owner()
    async def admin(self, ctx: commands.Context):
        if not ctx.invoked_subcommand:
            await ctx.reply(t(dict(
                ja="使用方法が違います。", en="It is wrong way to use this command."
            ), ctx))

    @admin.command(aliases=("rel", "再読み込み"), description="Reload something")
    @discord.app_commands.describe(choice="Something will be reloaded.")
    async def reload(self, ctx: commands.Context, *, choice: Literal["help"]):
        if choice == "help":
            await ctx.typing()
            await self.bot.cogs["Help"].aioload() # type: ignore
        else:
            return await ctx.reply(t(dict(
                ja="何をすれば良いかわかりません。", en="I don't know what to do."
            ), ctx))
        await ctx.reply("Ok")

    @admin.command(aliases=("db", "データベース"), description="Run sql")
    @discord.app_commands.describe(sql="SQL code")
    async def sql(self, ctx: commands.Context, *, sql: str):
        await ctx.typing()
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql)
                result = "\n".join(
                    map(lambda x: "\t".join(map(str, x)),
                    await cursor.fetchall())
                )
        if len(result) > 2000:
            embeds = []
            for text in separate(result):
                embeds.append(Cog.Embed("MySQL Result", description=code_block(text)))
            set_page(embeds)
            embeds = EmbedPage(embeds)
            embeds.set_message(
                ctx, await ctx.reply("Ok", embed=embeds.embeds[0], view=embeds)
            )
        else:
            await ctx.reply("Ok", embed=Cog.Embed(
                "MySQL Result", description=code_block(result)
            ))

    @admin.command(aliases=("su", "ヒトガワリ"), description="Let the command run as someone else.")
    @discord.app_commands.describe(member="Target member", command="Target command")
    async def insted(self, ctx: commands.Context, member: discord.Member, *, command: str):
        ctx.message.author = member
        ctx.message.content = f"{ctx.prefix}{command}"
        await self.bot.process_commands(ctx.message)

    @executor_function
    def make_monitor_embed(self):
        embed = Cog.Embed(
            title="RT Running Monitor",
            description=f"Running on {system()}",
        )
        embed.add_field(
            name="Memory",
            value=f"{psutil.virtual_memory().percent}%"
        )
        embed.add_field(
            name="CPU",
            value=f"{psutil.cpu_percent(interval=1)}%"
        )
        embed.add_field(
            name="Disk",
            value=f"{psutil.disk_usage('/').percent}%"
        )
        embed.add_field(name="Latency", value=self.bot.parsed_latency)
        embed.add_field(name="Pool", value=self.bot.pool.size)
        return embed

    @admin.command(aliases=("m", "モニター"), description="Displays CPU utilization, etc.")
    async def monitor(self, ctx: commands.Context):
        await ctx.typing()
        embed = await self.make_monitor_embed()
        embed.add_field(name="Tasks", value=len(all_tasks()))
        await ctx.reply(embed=embed)


async def setup(bot):
    await bot.add_cog(Admin(bot))
