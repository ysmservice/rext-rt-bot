# RT - General

from typing import Optional

from itertools import chain
from inspect import cleandoc

from discord.ext import commands, tasks
import discord

from rtlib.common.utils import make_error_message

from core.utils import make_default
from core.views import TimeoutView
from core.cacher import Cacher
from core.types_ import CmdGrp
from core.help import CONV, ANNOTATIONS
from core import RT, Cog, Embed, t

from rtlib.common.utils import code_block

from data import TEST, SUPPORT_SERVER, PERMISSION_TEXTS

from .help import HelpView


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


class ShowHelpView(TimeoutView):
    "ヘルプを表示するボタンのViewです。"

    def __init__(self, bot: RT, command: CmdGrp, label: tuple[str, str], *args, **kwargs):
        self.bot, self.command = bot, command
        super().__init__(*args, **kwargs)
        self.show.label = label[0]
        self.add_item(discord.ui.Button(
            label="Support Server", url=SUPPORT_SERVER, emoji="💬"
        ))

    @discord.ui.button(label="Show help", emoji="🔍")
    async def show(self, interaction: discord.Interaction, _):
        command = (
            self.command.root_parent or self.command.parent or self.command
        )
        view: HelpView = self.bot.cogs["Help"].make_view( # type: ignore
            self.bot.get_language("user", interaction.user.id),
            command.callback.__help__.category, command.name, # type: ignore
            interaction
        )
        view.target = interaction.user.id
        await interaction.response.send_message(
            embed=view.page.embeds[0], view=view, ephemeral=True
        )
        view.set_message(interaction)


class General(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.status_modes = ("guilds", "users")
        self.now_status_mode = "guilds"

        self._replied_caches: Cacher[int, list[str]] = \
            self.bot.cachers.acquire(5.0, list)

        self._dayly.start()

    @Cog.listener()
    async def on_ready(self):
        if not self.status_updater.is_running():
            self.status_updater.start()

    @tasks.loop(minutes=1)
    async def status_updater(self):
        # Update status
        if self.bot.is_ready():
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
        .update_headline(ja="RTのレイテンシを表示します。")

    @commands.command(description="Displays info of RT.")
    async def info(self, ctx: commands.Context):
        await ctx.reply(embed=Cog.Embed("RT Info", description=t(RT_INFO, ctx)))

    Cog.HelpCommand(info) \
        .set_description(ja="RTの情報を表示します。", en="Displays info of RT.") \
        .update_headline(ja="RTの情報を表示します。")

    async def clean(self):
        "セーブデータの掃除を行います。"
        if not self.bot.ipcs.ready.is_set():
            return

        for key in list(self.bot.cogs.keys()):
            function = None
            if hasattr(self.bot.cogs[key], "data") \
                    and hasattr(getattr(self.bot.cogs[key], "data"), "clean"):
                function = getattr(getattr(self.bot.cogs[key], "data"), "clean")
            elif hasattr(self.bot.cogs[key], "clean") \
                    and "cursor" in getattr(self.bot.cogs[key], "clean") \
                        .__code__.co_varnames:
                function = getattr(self.bot.cogs[key], "clean")
            if function is not None:
                self.bot.print("[Cleaner]", "Clean data: %s" % key)
                self.bot.loop.create_task(function(), name="Clean data")

    @tasks.loop(hours=1 if TEST else 24)
    async def _dayly(self):
        # 掃除をする。
        if not self.bot.shard_id:
            await self.clean()

    async def cog_unload(self):
        self.status_updater.cancel()
        self._dayly.cancel()

    STATUS_MESSAGES = {
        400: {"ja": "おかしいリクエスト", "en": "Bad Request"},
        403: {"ja": "権限エラー", "en": "Forbidden"},
        404: {"ja": "見つからないエラー", "en": "NotFound"},
        423: {"ja": "鍵がかかっています", "en": "Locked"},
        429: {"ja": "リクエスト過多", "en": "Too Many Requests"},
        500: {"ja": "内部エラー", "en": "Internal Server Error"}
    }

    async def reply_error(
        self, ctx: commands.Context, status: int,
        content: str, view: Optional[discord.ui.View] = None,
        color: str = "error"
    ):
        "エラーの返信を行う。"
        await ctx.reply(embed=discord.Embed(
            title="{} {}".format(
                status, t(self.STATUS_MESSAGES.get(status, {'ja': 'エラー', 'en': 'Error'}), ctx)
            ), description=content,
            color=getattr(self.bot.Colors, color)
        ), view=view)

    BAD_ARGUMENT = staticmethod(lambda ctx, code: t(dict(
        ja="引数がおかしいです。\nCode:`{code}`", en="The argument format is incorrect.\nCode:`{code}`"
    ), ctx, code=code))

    @commands.Cog.listener()
    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError | Exception,
        retry: bool = False
    ):
        # エラーハンドリングをします。
        if not retry:
            # 既に五秒以内に返信をしているのなら返信を行わない。
            name = getattr(ctx.command, "name", "")
            if name in self._replied_caches[ctx.author.id]:
                if hasattr(error, "retry_after"):
                    # クールダウン告知後十秒以内にもう一度コマンドが実行された場合、クールダウンが終わるまでクールダウン告知を返信しないようにする。
                    self._replied_caches.get_raw(ctx.author.id) \
                        .update_deadline(error.retry_after) # type: ignore
                return
            elif name:
                self._replied_caches[ctx.author.id].append(name)

        # デフォルトのViewを用意しておく。
        view = None
        if ctx.command is not None:
            view = ShowHelpView(self.bot, ctx.command, (
                t(dict(ja="ヘルプを見る。", en="Show help"), ctx),
                t(dict(ja="サポートサーバー", en="Support Server"), ctx)
            ))
        content, status = None, 400

        # エラーハンドリングを行う。
        if isinstance(error, commands.CommandInvokeError) and not retry:
            return await self.on_command_error(ctx, error.original, True)
        elif isinstance(error, AssertionError):
            if isinstance(error.args[0], tuple):
                status, content = error.args[0]
            else:
                content = error.args[0]
            if isinstance(content, dict):
                content = t(content, ctx)
        elif isinstance(error, commands.UserInputError):
            content = self.BAD_ARGUMENT(ctx, error)
            if isinstance(error, commands.MissingRequiredArgument):
                content = t(dict(
                    ja="引数が足りません。", en="Argument is missing."
                ), ctx)
            elif isinstance(error, commands.BadArgument):
                if error.__class__.__name__.endswith("NotFound"):
                    status = 404
                    key = error.__class__.__name__
                    kind = t(ANNOTATIONS.get(key, make_default(key)), ctx)
                    for value in CONV.values():
                        kind = kind.replace(value, "")
                    content = t(dict(
                        ja="期待される値の種類：{kind}", en="Expected Kind of Value: {kind}"
                    ), ctx, kind=kind)
                elif isinstance(error, commands.ChannelNotReadable):
                    content = t(dict(
                        ja="指定されたチャンネルが見えません。", en="The specified channel is not visible."
                    ), ctx)
                elif isinstance(error, commands.BadColourArgument):
                    content = t(dict(
                        ja="指定された色がおかしいです。", en="The specified color is wrong."
                    ), ctx)
                elif isinstance(error, commands.BadBoolArgument):
                    content = t(dict(
                        ja="真偽地がおかしいです。\n有効な真偽地：True/False, on/off, 1/0",
                        en="The specified boolean value is wrong.\nValid Values: True/False, on/off, 1/0"
                    ))
                elif isinstance(error, (commands.BadUnionArgument, commands.BadLiteralArgument)):
                    if isinstance(error, commands.BadLiteralArgument):
                        extra = "\n{}".format(t(
                            {"ja": "有効な選択肢：`{literals}`", "en": "Valid Items: `{literals}`"},
                            ctx, literals='`, `'.join(error.literals)
                        ))
                    else:
                        extra = ""
                    content = t(dict(
                        ja="引数{name}に無効な引数が渡されました。{extra}",
                        en="Invalid argument was passed for argument {name}.{extra}"
                    ), ctx, name=error.param.name, extra=extra)
        elif isinstance(error, commands.CheckFailure):
            if isinstance(error, commands.PrivateMessageOnly):
                content = t(dict(
                    ja="プライベートな場所でしかこのコマンドは実行することができません。",
                    en="This command can only be executed in a private location."
                ), ctx)
            elif isinstance(error, commands.NoPrivateMessage):
                content = t(dict(
                    ja="プライベートな場所でこのコマンドは実行することはできません。",
                    en="This command cannot be executed in a private location."
                ), ctx)
            elif isinstance(error, commands.CheckAnyFailure):
                content = t(dict(
                    ja="RTの管理者以外はこのコマンドを実行できません。",
                    en="Only the RT administrator can execute this command."
                ), ctx)
            elif isinstance(error, commands.MissingPermissions):
                content = t(dict(
                    ja="あなたにこのコマンドの実行に必要な権限がないので、このコマンドを実行できません。\n必要な権限：{perms}",
                    en="You do not have the necessary permissions to execute this command, so we cannot execute this command.\nRequired Permissions: {perms}"
                ), ctx, perms=", ".join(
                    t(PERMISSION_TEXTS.get(key, make_default(key)), ctx)
                    for key in error.missing_permissions
                ))
            elif isinstance(error, commands.NSFWChannelRequired):
                content = t(dict(
                    ja="このコマンドはNSFWチャンネルでなければ実行することができません。",
                    en="This command can only be executed on NSFW channels."
                ), ctx)
        elif isinstance(error, commands.CommandOnCooldown):
            status = 429
            content = t(dict(
                ja="クールダウン中です。\n{seconds:.2f}秒お待ちください。",
                en="It is currently on cool down.\nPlease wait for {seconds:.2f}s."
            ), ctx, seconds=error.retry_after)
        elif isinstance(error, commands.MaxConcurrencyReached):
            name = getattr(ctx.command, "name", "")
            content = t(dict(
                ja="これ以上このコマンドを実行することはできません。",
                en="No further execution of this command is allowed."
            ), ctx)
        elif isinstance(error, commands.CommandNotFound):
            view = None
            # `もしかして：`を提案する。
            suggestion = "`, `".join(
                command.name for command in self.bot.commands
                if any(
                    any(
                        len(cmd_name[i:i + 3]) > 2
                        and cmd_name[i:i + 3] in ctx.message.content
                        for i in range(3)
                    ) for cmd_name in chain(
                        (command.name,), command.aliases
                    )
                )
            )
            if len(suggestion) > 150:
                suggestion = ""
            if suggestion:
                suggestion = "\n{}`{}`".format(
                    t({'ja': 'もしかして：', 'en': 'Perhaps: '}, ctx), suggestion
                )
            content = t(dict(
                ja="コマンドが見つかりませんでした。{suggestion}", en="That command is not found.{suggetion}"
            ), ctx, suggestion=suggestion)
            status = 404

        if content is None:
            # 不明なエラーが発生した場合
            # エラーの全文を生成する。
            error_message = make_error_message(error)
            setattr(ctx, "__rt_error__", error_message)
            # ログを出力しておく。
            if TEST:
                self.bot.print(error_message)
            else:
                self.bot.print("Warning: An error has occurred: {} - {}\n\tCommand: {}".format(
                    error.__class__.__name__, error,
                    ctx.message.content if ctx.command is None else ctx.command.qualified_name
                ))
            status = 500
            content = code_block(error_message, "python")

        self.bot.dispatch("command_error_review", status, content, ctx, error)
        await self.reply_error(
            ctx, status, content, view,
            "unknown" if view is None else "error"
        )


async def setup(bot):
    await bot.add_cog(General(bot))