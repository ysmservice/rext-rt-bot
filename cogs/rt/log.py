# RT - Log

from __future__ import annotations

from typing import Literal, Any

from discord.ext import commands
import discord

from rtlib.views import BasePage, PageMode
from rtlib.utils import get_name_and_id_str, truncate, code_block
from rtlib.log import LogData
from rtlib import RT, Cog, t


class LogViewerView(BasePage):
    def __init__(self, cog: RTLog, id_: int, *args, **kwargs):
        self.cog, self.id_ = cog, id_
        self.enable_lock = True
        super().__init__(*args, **kwargs)

    async def make_embed(self, ctx: Any) -> discord.Embed:
        "埋め込みを作ります。"
        # データを集める。
        datas: list[LogData] = []
        async with self.cog.bot.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT * FROM Log WHERE Id = %s ORDER BY Time DESC LIMIT %s, 10;",
                    (self.id_, self.page * 10)
                )
                for row in await cursor.fetchall():
                    datas.append(self.cog.bot.log.data.row_to_data(row))
        # 埋め込みを作る。
        embed = self.cog.Embed(
            title=t({"ja": "RT イベントログ", "en": "RT Event Log"}, ctx)
        )
        for data in datas:
            embed.add_field(
                name=data.title(self.cog.bot.get_language("user", self.target)), # type: ignore
                value=truncate(data.to_str("", False)), inline=False
            )
        embed.set_footer(text=t(dict(
            ja="より詳細を見たい場合は、ダッシュボードからご覧ください。",
            en="If you would like to see more details, please visit the dashboard."
        ), ctx))
        if not datas:
            embed.description = "この先はもうありません。"
            self.lock = True
        return embed

    async def on_turn(self, mode: PageMode, interaction: discord.Interaction) -> bool:
        if not await super().on_turn(mode, interaction):
            self.set_message(interaction)
            await interaction.response.edit_message(
                embed=await self.make_embed(interaction), view=self
            )
        return True


class RTLog(Cog):
    def __init__(self, bot: RT):
        self.bot = bot

    @commands.group(description="RT Log Management Commands")
    @commands.has_permissions(administrator=True)
    async def rtlog(self, ctx: commands.Context):
        if not ctx.invoked_subcommand:
            await ctx.reply(Cog.ERRORS["WRONG_WAY"](ctx))

    @rtlog.command(description="Show RT Log")
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def show(self, ctx: commands.Context):
        view = LogViewerView(self, ctx.author.id if ctx.guild is None else ctx.guild.id)
        view.target = ctx.author.id
        view.set_message(ctx, await ctx.reply(embed=await view.make_embed(ctx), view=view))

    @rtlog.command(description="Clear RT Log")
    @commands.cooldown(1, 15, commands.BucketType.guild)
    async def clear(self, ctx: commands.Context):
        await ctx.trigger_typing()
        await self.bot.log.data.clear(ctx.author.id if ctx.guild is None else ctx.guild.id)
        await ctx.reply("Ok")

    @commands.Cog.listener()
    async def on_command_error_review(
        self, status: int, content: str, ctx: commands.Context, _: str
    ):
        await self.command_log(ctx, "UNKNOWN" if status == 404 else "ERROR",
            "\nResult:\n%s" % code_block(getattr(ctx, "__rt_error__"), "python")
                if status == 500 else content)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        await self.command_log(ctx, "SUCCESS")

    async def command_log(self, ctx: commands.Context, mode: str, extra: str = ""):
        "コマンドのログを流します。"
        feature = None
        if ctx.command is not None:
            feature = ctx.command.root_parent or ctx.command
        if feature is None:
            feature = ("...", ctx.message.content)
        await self.bot.log(self.bot.log.LogData.quick_make(
            feature, getattr(self.bot.log.ResultType, mode),
            ctx.guild or ctx.author, t(dict(
                ja="実行者：{author}\nチャンネル：{channel}\nコマンドの引数：\n{kwargs}{extra}",
                en="User:{author}\nChannel: {channel}\nCommand Arguments:\n{kwargs}{extra}"
            ), ctx.guild, author=get_name_and_id_str(ctx.author),
            channel=get_name_and_id_str(ctx.channel),
            kwargs=code_block("\n".join(
                f"{key}\t{'' if value is None else value}"
                for key, value in ctx.kwargs.items()
            )) if ctx.kwargs else "...", extra=extra), ctx=ctx
        ))

    (Cog.HelpCommand(rtlog)
        .update_headline(ja="RTのログの管理コマンドです。")
        .set_description(
            ja="このコマンドは、RTのログを見たり消したりするためのコマンドです。\nRTのログは、実行されたコマンドや裏で行われた処理の内容と結果を記録したものです。",
            en="This command can be used to see RT log and clear RT log.\nRT's logs are a record of the contents and results of the commands executed and the processing that took place behind the scenes."
        )
        .set_extra("Notes",
            ja="RTのログはダッシュボードからも見ることができます。\nダッシュボードでは絞り込み機能があり見やすいです。"
        )
        .add_sub(Cog.HelpCommand(show)
            .set_description(ja="RTのログを表示します。", en="Displays logs of RT.")
            .set_extra(
                "Notes", ja="細かくは表示されません。\n詳細を見たい場合はダッシュボードから見てください。",
                en="It is not shown in detail. \nIf you want to see the details, please look at it from the dashboard."
            ))
        .add_sub(Cog.HelpCommand(clear)
            .set_description(ja="RTのログを消します。", en="Clear logs of RT")))


class DiscordLog(Cog):
    def __init__(self, bot: RT):
        self.bot = bot


async def setup(bot):
    await bot.add_cog(RTLog(bot))
    await bot.add_cog(DiscordLog(bot))