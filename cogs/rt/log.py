# RT - Log

from __future__ import annotations

from typing import ParamSpec, TypeVar, Optional, Any
from collections.abc import Callable, Coroutine

from functools import wraps

from discord.ext import commands, tasks
import discord

from core.utils import truncate, make_default, concat_text
from core.types_ import Text
from rtlib.common.cacher import Cacher
from core.log import LogData
from core import RT, Cog, t

from rtlib.common.utils import code_block

from rtutil.views import BasePage, PageMode


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
                value=truncate(data.to_str("", False)) or "...", inline=False
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
        await ctx.typing()
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
            if isinstance(ctx.command, discord.app_commands.ContextMenu):
                feature = ctx.command
            else:
                feature = ctx.command.root_parent or ctx.command
        if feature is None:
            feature = ("...", ctx.message.content)
        await self.bot.log(self.bot.log.LogData.quick_make(
            feature, getattr(self.bot.log.ResultType, mode),
            ctx.guild or ctx.author, t(dict(
                ja="実行者：{author}\nチャンネル：{channel}\nコマンドの引数：\n{kwargs}{extra}",
                en="User:{author}\nChannel: {channel}\nCommand Arguments:\n{kwargs}{extra}"
            ), ctx.guild, author=self.name_and_id(ctx.author),
            channel=self.name_and_id(ctx.channel), # type: ignore
            kwargs=code_block("\n".join(
                f"{key}\t{'' if value is None else value}"
                for key, value in ctx.kwargs.items()
            )) if ctx.kwargs else "...\n", extra=extra), ctx=ctx
        ))

    (Cog.HelpCommand(rtlog)
        .merge_headline(ja="RTのログの管理コマンドです。")
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


LFnReT = TypeVar("LFnReT", bound=Callable[..., Coroutine])
LFnPT = ParamSpec("LFnPT")
def log(attr: str = "guild", arg: int = 0):
    def deco(func: Callable[LFnPT, Any]) -> Callable[LFnPT, Coroutine]:
        @wraps(func)
        async def new(*args: LFnPT.args, **kwargs: LFnPT.kwargs):
            self: DiscordLog = args[0] # type: ignore
            args = args[1:] # type: ignore
            if isinstance(args[arg], discord.Guild):
                channel = self.get_log_channel(args[arg]) # type: ignore
            else:
                try:
                    channel = self.get_log_channel(getattr(args[arg], attr))
                except AttributeError:
                    channel = None
            if channel is not None:
                args += (channel,) # type: ignore
                return await func(self, *args, **kwargs) # type: ignore
        return new
    return deco


NAME_TEXT = {"ja": "名前", "en": "Name"}
ADD_TEXT = {"ja": "追加", "en": "Add"}
REMOVE_TEXT = {"ja": "削除", "en": "Remove"}
UPDATE_TEXT = {"ja": "更新", "en": "Update"}
ADD_REMOVE_TEXT = {"ja": "追加/削除", "en": "Add/Remove"}
UPDATE_ADD_REMOVE_TEXT = concat_text(ADD_REMOVE_TEXT, {"ja": "更新", "en": "Update"}, "/")
CREATE_TEXT = {"ja": "作成", "en": "Create"}
DELETE_TEXT = {"ja": "削除", "en": "Delete"}
CREATE_DELETE_TEXT = {"ja": "作成/削除", "en": "Create/Delete"}
UPDATE_CREATE_DELETE_TEXT = concat_text(CREATE_DELETE_TEXT, {"ja": "更新", "en": "Update"}, "/")
BEFORE_TEXT = {"ja": "前", "en": "Before"}
AFTER_TEXT = {"ja": "後", "en": "After"}


class DiscordLog(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.caches: Cacher[discord.TextChannel, list[discord.Embed]] = \
            self.bot.cachers.acquire(30.0, list)
        self.send_log.start()

    @commands.Cog.listener()
    async def on_help_load(self):
        self.bot.help_.set_help(Cog.Help()
            .set_category("server-management")
            .set_title("log")
            .set_headline(ja="Discordのログを出力します。", en="Outputs Discord logs.")
            .set_description(
                ja="""チャンネルプラグインです。
                    Discordのログを出力したいチャンネルのトピックに`rt>log`を書き込んでください。
                    そしたら、そのチャンネルにログが流れるようになります。""",
                en="""Channel plug-ins.
                    Write `rt>log` to the topic of the channel you want to output Discord logs.
                    Then, the log will be played on that channel."""
            )
        )

    @tasks.loop(seconds=5)
    async def send_log(self):
        for channel, embeds in list(self.caches.items()):
            if embeds:
                try:
                    await channel.send(embeds=embeds[:10])
                    if embeds := embeds[10:]:
                        await channel.send(embeds=embeds[:10])
                except Exception as e:
                    self.bot.ignore(e, "\nEmbed:", embeds[int(str(e).split(".")[1])].title)
            del self.caches[channel]

    async def cog_unload(self):
        self.send_log.cancel()

    def get_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        "ログチャンネルを検索します。"
        for channel in guild.text_channels:
            if channel.topic is not None and "rt>log" in channel.topic:
                return channel

    def get_channel_type(self, mode: str, channel: discord.abc.GuildChannel) -> Text:
        "チャンネルの種類の文字列を作ります。"
        if mode == "create":
            end = {"ja": "作成", "en": "Create"}
        elif mode == "delete":
            end = {"ja": "削除", "en": "Delete"}
        elif mode == "update":
            end = {"ja": "更新", "en": "Update"}
        else:
            end = make_default("")
        if isinstance(channel, discord.TextChannel):
            new = {"ja": "テキストチャンネル", "en": "Text Channel "}
        elif isinstance(channel, discord.VoiceChannel):
            new = {"ja": "ボイスチャンネル", "en": "Voice Channel "}
        elif isinstance(channel, discord.CategoryChannel):
            new = {"ja": "カテゴリー", "en": "Category "}
        elif isinstance(channel, discord.StageChannel):
            new = {"ja": "ステージチャンネル", "en": "Stage Channel "}
        elif isinstance(channel, discord.ForumChannel):
            new = {"ja": "フォーラムチャンネル", "en": "Forum Channel "}
        else:
            new = {"ja": "チャンネル", "en": "Channel "}
        return concat_text(end, new, ": ")

    @commands.Cog.listener()
    @log()
    async def on_guild_channel_delete(
        self, channel: discord.abc.GuildChannel, logc: discord.TextChannel
    ):
        await self.on_guild_channel("delete", channel, logc)

    @commands.Cog.listener()
    @log()
    async def on_guild_channel_create(
        self, channel: discord.abc.GuildChannel, logc: discord.TextChannel
    ):
        await self.on_guild_channel("create", channel, logc)

    @commands.Cog.listener()
    @log()
    async def on_guild_channel_update(
        self, _: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
        logc: discord.TextChannel
    ):
        await self.on_guild_channel("update", after, logc)

    async def on_guild_channel(
        self, mode: str,
        channel: discord.abc.GuildChannel,
        logc: discord.TextChannel
    ):
        self.caches[logc].append(Cog.Embed(
            t(self.get_channel_type(mode, channel), channel.guild),
            description=channel.mention
        ).add_field(name=t(NAME_TEXT, logc.guild), value=channel.name))

    @commands.Cog.listener()
    @log()
    async def on_guild_channel_pins_update(
        self, channel: discord.abc.GuildChannel | discord.Thread, _,
        logc: discord.TextChannel
    ):
        self.caches[logc].append(Cog.Embed(
            t({"ja": "ピン留めの追加または削除", "en": "Add or remove pinning"}, logc.guild)
        ).add_field(
            name=t({"ja": "場所", "en": "Place"}, logc.guild),
            value=channel.mention
        ))

    @commands.Cog.listener()
    @log()
    async def on_guild_update(
        self, before: discord.Guild, after: discord.Guild,
        logc: discord.TextChannel
    ):
        embed = Cog.Embed(
            t({"ja": "サーバーの情報更新", "en": "Server information updated"}, logc.guild)
        )
        if before.name == after.name and before.name:
            self.caches[logc].append(
                embed.add_field(name=t(BEFORE_TEXT, logc.guild), value=before.name)
                    .add_field(name=t(AFTER_TEXT, logc.guild), value=after.name)
            )
        else:
            self.caches[logc].append(embed)

    def on_update(self, log_type: str, type_: Text, logc: discord.TextChannel):
        self.caches[logc].append(Cog.Embed(
            t(globals()[f"{log_type}_TEXT"], logc.guild),
            description=t(type_, logc.guild)
        ))

    @commands.Cog.listener()
    @log()
    async def on_guild_emojis_update(
        self, _, __, ___, logc: discord.TextChannel
    ):
        self.on_update("ADD_REMOVE", {"ja": "絵文字", "en": "Emoji"}, logc)

    @commands.Cog.listener()
    @log()
    async def on_guild_stickers_update(self, _, __, ___, logc: discord.TextChannel):
        self.on_update("ADD_REMOVE", {"ja": "スタンプ", "en": "Sticker"}, logc)

    def make_invite_text(self, invite: discord.Invite) -> Text:
        return {
            "ja": f"招待リンク：{invite.url}", "en": f"Invite Link: {invite.url}"
        }

    @commands.Cog.listener()
    @log()
    async def on_invite_create(self, invite: discord.Invite, logc: discord.TextChannel):
        self.on_update("CREATE", self.make_invite_text(invite), logc)

    @commands.Cog.listener()
    @log()
    async def on_invite_delete(self, invite: discord.Invite, logc: discord.TextChannel):
        self.on_update("REMOVE", self.make_invite_text(invite), logc)

    @commands.Cog.listener()
    @log()
    async def on_guild_integrations_update(self, _, logc: discord.TextChannel):
        self.on_update("UPDATE_ADD_REMOVE", {"ja": "サーバー連携", "en": "Integration"}, logc)

    @commands.Cog.listener()
    @log()
    async def on_webhooks_update(self, _, logc: discord.TextChannel):
        self.on_update("UPDATE_ADD_REMOVE", make_default("Webhook"), logc)

    def make_embed(self, type_: Text, guild: discord.Guild, **kwargs):
        return Cog.Embed(t(type_, guild), **kwargs)

    def on_member(self, member: discord.Member, type_: Text, logc: discord.TextChannel):
        self.caches[logc].append(self.make_embed(
            type_, member.guild,
            description=self.name_and_id(member)
        ).set_thumbnail(url=getattr(member.avatar, "url", "")))

    @commands.Cog.listener()
    @log()
    async def on_member_join(self, member: discord.Member, logc: discord.TextChannel):
        self.on_member(member, {"ja": "メンバーの入室", "en": "Join Member"}, logc)

    @commands.Cog.listener()
    @log()
    async def on_member_remove(self, member: discord.Member, logc: discord.TextChannel):
        self.on_member(member, {"ja": "メンバーの退出", "en": "Remove Member"}, logc)

    @commands.Cog.listener()
    @log()
    async def on_member_update(self, _, after: discord.Member, logc: discord.TextChannel):
        self.on_update("UPDATE", {
            "ja": f"メンバー: {after.mention}", "en": f"Member: {after.mention}"
        }, logc)

    def on_member_punish(
        self, guild: discord.Guild, user: discord.User,
        logc: discord.TextChannel, mode: str
    ):
        self.caches[logc].append(self.make_embed(
            make_default(mode), guild,
            description=self.name_and_id(user)
        ))

    @commands.Cog.listener()
    @log()
    async def on_member_ban(
        self, guild: discord.Guild, user: discord.User,
        logc: discord.TextChannel
    ):
        self.on_member_punish(guild, user, logc, "Ban")

    @commands.Cog.listener()
    @log()
    async def on_member_unban(
        self, guild: discord.Guild, user: discord.User,
        logc: discord.TextChannel
    ):
        self.on_member_punish(guild, user, logc, "Kick")

    @commands.Cog.listener()
    @log()
    async def on_message_edit(
        self, before: discord.Message, after: discord.Message,
        logc: discord.TextChannel
    ):
        if after.guild is not None:
            embed = self.make_embed(
                {"ja": "メッセージの編集", "en": "Edit Message"}, after.guild,
                description=after.jump_url
            )
            if before.content != after.content:
                if before.content:
                    embed.add_field(
                        name=t(BEFORE_TEXT, logc.guild), value=before.content
                    )
                if after.content:
                    embed.add_field(
                        name=t(AFTER_TEXT, logc.guild), value=after.content
                    )
            self.caches[logc].append(embed)

    def on_message(self, message: discord.Message) -> Text:
        return {
            "ja": f"メッセージ:\n{message.content}", "en": f"Message:\n{message.content}"
        }

    @commands.Cog.listener()
    @log()
    async def on_message_delete(self, message: discord.Message, logc: discord.TextChannel):
        self.on_update("REMOVE", self.on_message(message), logc)

    @commands.Cog.listener()
    @log()
    async def on_reaction_clear(
        self, message: discord.Message, _, logc: discord.TextChannel
    ):
        self.on_update("REMOVE", concat_text({
            "ja": "全てのリアクション", "en": "全てのリアクション"
        }, self.on_message(message), "\n"), logc)

    def on_role(self, mode: str, role: discord.Role, logc: discord.TextChannel):
        self.on_update(mode, {
            "ja": f"ロール：{self.name_and_id(role)}",
            "en": f"Role: {self.name_and_id(role)}"
        }, logc)

    @commands.Cog.listener()
    @log()
    async def on_guild_role_create(self, role: discord.Role, logc: discord.TextChannel):
        self.on_role("CREATE", role, logc)

    @commands.Cog.listener()
    @log()
    async def on_guild_role_delete(self, role, logc: discord.TextChannel):
        self.on_role("DELETE", role, logc)

    @commands.Cog.listener()
    @log()
    async def on_guild_role_update(self, _, after: discord.Role, logc: discord.TextChannel):
        self.on_role("UPDATE", after, logc)

    def on_schedule(self, event: discord.ScheduledEvent) -> Text:
        return {
            "ja": f"スケジュール：{self.name_and_id(event)}",
            "en": f"Schedule: {self.name_and_id(event)}"
        }

    @commands.Cog.listener()
    @log()
    async def on_scheduled_event_create(
        self, event: discord.ScheduledEvent, logc: discord.TextChannel
    ):
        self.on_update("CREATE", self.on_schedule(event), logc)

    @commands.Cog.listener()
    @log()
    async def on_scheduled_event_update(
        self, _, after: discord.ScheduledEvent, logc: discord.TextChannel
    ):
        self.on_update("UPDATE", self.on_schedule(after), logc)

    def on_thread(
        self, mode: str, thread: discord.Thread,
        logc: discord.TextChannel, mention: bool = True
    ):
        if mention:
            t = self.mention_and_id(thread)
        else:
            t = self.name_and_id(thread)
        self.on_update(mode, {"ja": f"スレッド：{t}", "en": f"Thread: {t}"}, logc)

    @commands.Cog.listener()
    @log()
    async def on_thread_create(self, thread: discord.Thread, logc: discord.TextChannel):
        self.on_thread("CREATE", thread, logc)

    @commands.Cog.listener()
    @log()
    async def on_thread_delete(self, thread: discord.Thread, logc: discord.TextChannel):
        self.on_thread("DELETE", thread, logc, False)

    @commands.Cog.listener()
    @log()
    async def on_thread_update(self, _, after: discord.Thread, logc: discord.TextChannel):
        self.on_thread("UPDATE", after, logc)


async def setup(bot):
    await bot.add_cog(RTLog(bot))
    await bot.add_cog(DiscordLog(bot))