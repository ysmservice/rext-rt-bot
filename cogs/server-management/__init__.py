# RT - Server Management

from datetime import datetime, timedelta

from discord.ext import commands
import discord
from orjson import loads

from core import RT, Cog, t

from rtlib.common.utils import code_block
from rtlib.common.json import dumps

from rtutil.collectors import make_google_url
from rtutil.content_data import ContentData
from rtutil.views import TimeoutView

from data import TOPIC_PREFIX


FSPARENT = "server-management"


def swith_replace(
    text: str, parts: tuple[str, ...],
    mode: str = "starts", language: str = "ja"
) -> str:
    """渡された文字列達のどれかで指定された文字列の最初または最後にある文字列を探します。
    また、見つけた文字列を削除します。"""
    for part in parts:
        if (mode == "starts" and text.startswith(part)) \
                or text.endswith(part):
            if language == "en":
                if not text.endswith("?"):
                    continue
                # 最後のクエスチョンマークを消す。
                text = text[:-1]
            if mode == "starts":
                return text[len(part):]
            else:
                return text[:-len(part)]
    return text


class SearchResultShowButton(discord.ui.Button):
    "検索結果をみんなが見える状態にするかを聞くボタンです。"

    def __init__(self, content: str, message: discord.Message, *args, **kwargs):
        self.content, self.message = content, message
        kwargs.setdefault("style", discord.ButtonStyle.blurple)
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        assert self.view is not None
        self.view.remove_item(self.view.children[1])
        await self.message.reply(
            t(dict(
                ja="{mention}により検索が行われました。\n{content}",
                en="The search was performed by {mention} command.\n{content}"
            ), interaction, mention=interaction.user.mention, content=self.content),
            allowed_mentions=discord.AllowedMentions.none(), view=self.view
        )


class ServerManagement(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self._CTX_MES_SEARCH = "Search"
        self._CTX_MES_GC = "Get Content"
        self.bot.tree.add_command(discord.app_commands.ContextMenu(
            name=self._CTX_MES_SEARCH, callback=self.search,
            type=discord.AppCommandType.message
        ))
        self.bot.tree.add_command(discord.app_commands.ContextMenu(
            name=self._CTX_MES_GC, callback=self.get_content,
            type=discord.AppCommandType.message
        ))

    async def cog_unload(self):
        self.bot.tree.remove_command(self._CTX_MES_SEARCH)
        self.bot.tree.remove_command(self._CTX_MES_GC)

    @commands.Cog.listener()
    async def on_help_load(self):
        self.bot.help_.set_help(Cog.Help()
            .set_title(self._CTX_MES_SEARCH)
            .set_headline(ja="お手軽検索", en="Easliy search")
            .set_description(
                ja="""検索したいメッセージのコンテキストメニューのアプリの`Search`を押すことで、Googleの検索のURLを作ります。
                「とは」が後ろについている場合はそれを消して検索をします。""",
                en="Create a Google search URL by pressing `Search` on the app in the context menu of the message you want to search."
            )
            .set_category(FSPARENT))
        self.bot.help_.set_help(Cog.Help()
            .set_title(self._CTX_MES_GC)
            .set_headline(ja="メッセージの内容のコードを取得します。", en="Get message content code")
            .set_description(
                ja="""メッセージの内容を表すコードを取得します。
                    一部の機能は、これで取得したコードでメッセージ内容を指定することができます。
                    もし、埋め込みや既にあるメッセージの内容をコマンドに使いたい場合は、もしかしたらこれでできるかもしれません。
                    例：`command`""",
                en="""Gets the code that represents the content of the message.
                    Some functions can specify the message content with the code retrieved with this.
                    If you want to use the content of an already existing message in a command, perhaps this can do it.
                    Example: `command`"""
            )
            .set_extra("Notes",
                ja="製品版を購入している場合は、これで取得したコードに埋め込みが含まれます。",
                en="If you have purchased the commercial version, the embedding will be included in the code you get with this.")
            .set_category(FSPARENT))
        self.bot.help_.set_help(Cog.Help()
            .set_title("autoPublish")
            .set_category(FSPARENT)
            .set_headline(ja="自動公開", en="Auto publish on news channel")
            .set_description(
                ja="""自動でニュースチャンネルのメッセージを公開します。
                    ニュースチャンネルのトピックに`rt>autoPublish`と入れることでできます。""",
                en="""Automatically publish messages on news channels.
                    You can do this by putting `rt>autoPublish` in the news channel topic."""
            ))
        self.bot.help_.set_help(Cog.Help()
            .set_title("autoThread")
            .set_category(FSPARENT)
            .set_headline(ja="自動スレッド作成チャンネル", en="Automatic Thread Creation Channel")
            .set_description(
                ja="""送られたメッセージから自動でスレッドを作成するチャンネルを作る機能です。
                `rt>thread`をチャンネルトピックに入れれば有効になります。""",
                en="""The ability to create a channel that automatically creates threads from messages sent to it.
                Put `rt>thread` in the channel topic to enable it."""
            )
            .set_extra("Notes",
                ja="""これを使うとチャンネルのスローモードは自動的に`10`秒に設定されます。
                スローモードが`10`秒より小さい場合、この機能は使えません。
                これは、誰かがメッセージを連続して投稿しているときに、たくさんのスレッドを作ってしまい、Discord が怒ってしまうのを避けるためです。""",
                en="""This will automatically set the channel's slow mode to `10` seconds.
                If the slow mode is lower than `10` seconds, this function cannot be used.
                This is to avoid creating a lot of threads when someone is posting messages in a row, which will make Discord angry."""))

    async def get_content(self, interaction: discord.Interaction, message: discord.Message):
        data = ContentData(content={}, author=message.author.id, json=True)
        if message.content:
            data["content"]["content"] = message.content
        assert interaction.guild_id is not None
        if message.embeds and await self.bot.customers.check(interaction.guild_id):
            data["content"]["embeds"] = [embed.to_dict() for embed in message.embeds]
        await interaction.response.send_message(
            code_block(dumps(data), "json"),
            allowed_mentions=discord.AllowedMentions.none()
        )

    QUESTIONS_JA = (
        "とは", "とは?", "とは？", "って何", "って何？",
        "って何?", "ってなに", "ってなに？", "ってなに?"
    )
    QUESTIONS_EN = (
        "what is ", "what's ", "What is ", "What's "
    )
    QUESTIONS = QUESTIONS_JA + QUESTIONS_EN

    async def search(self, interaction: discord.Interaction, message: discord.Message):
        language = self.bot.search_language(
            interaction.guild_id, message.author.id
        )
        # もし「とは」などと最後にあるメッセージの場合はそれを消す。
        content = swith_replace(
            message.content, self.QUESTIONS,
            "ends" if language == "ja" else "starts",
            language
        )
        # 検索URLを作って返信をする。
        view = TimeoutView()
        view.add_item(discord.ui.Button(label=t(dict(
            ja="検索結果を開く", en="Open result"
        ), interaction), url=make_google_url(content)))
        if len(getattr(view.children[0], "url")) > 512:
            await interaction.response.send_message(t(dict(
                ja="長すぎて検索できませんでした。", en="Too long to search."
            ), interaction), ephemeral=True)
        else:
            view.add_item(SearchResultShowButton(t(dict(
                    ja="このメッセージの検索結果を生成しました。",
                    en="I generated search results for this message."
                ), interaction), message, label=t(dict(
                    ja="みんなに見せる", en="Show for everyone"
            ), interaction)))
            await interaction.response.send_message(
                getattr(view.children[1], "content"), ephemeral=True, view=view
            )

    @commands.command(
        aliases=("msgc", "メッセージカウント", "メッセージ数"), fsparent=FSPARENT,
        description="Count the number of messages in the channel up to 5,000."
    )
    @commands.cooldown(1, 600, commands.BucketType.channel)
    @discord.app_commands.describe(content="The characters that must be included in the message to be counted. If not specified, all are included.")
    async def messagecount(self, ctx: commands.Context, *, content: str | None = None):
        message = await ctx.reply(t({"ja": "数え中...", "en": "Counting..."}, ctx))
        count = len([
            mes async for mes in ctx.channel.history(limit=5000)
            if content is None or content in mes.content
        ])
        await message.edit(content=t(dict(
            ja="メッセージ数：{count}", en="Message Count: {count}"
        ), ctx, count='5000⬆️' if count == 5000 else count))

    ((MESC_HELP := Cog.HelpCommand(messagecount))
        .merge_headline(
            ja="チャンネルのメッセージを五千個まで数え上げます。",
            en=messagecount.description
        )
        .set_description(**MESC_HELP.headline)
        .add_arg("content", "str", "Optional",
            ja="""数えるメッセージに含まれなければならない文字列を指定できます。
                未入力の場合は全てのメッセージが数える対象となります。""",
            en="""You can specify a string of characters that must be included in the message to be counted.
                If not entered, all messages will be counted."""))
    del MESC_HELP

    @commands.command(
        aliases=("ca", "送信者変更", "そへ"), fsparent=FSPARENT,
        description="Change the sender of the content code."
    )
    @discord.app_commands.describe(
        member=(_d_m := "The sender of the change."),
        code=(_d_c := "Content code")
    )
    async def change_author(self, ctx: commands.Context, member: discord.Member, *, code: str):
        assert ctx.guild is not None
        await self.bot.customers.assert_(ctx.guild.id)
        data: ContentData = loads(code)
        data["author"] = member.id
        await ctx.reply(
            code_block(dumps(data), "json"),
            allowed_mentions=discord.AllowedMentions.none()
        )

    (Cog.HelpCommand(change_author)
        .merge_description("headline", en="コンテンツコードの送信者を変更します。")
        .for_customer()
        .add_arg("member", "Member", ja="変更先の送信者です。", en=_d_m)
        .add_arg("code", "str", ja="コンテンツコードです。", en=_d_c))
    del _d_m, _d_c

    @commands.command(
        aliases=("tm", "タイムマシン", "バック・トゥ・ザ・フューチャー"), fsparent=FSPARENT,
        description="Displays jump URLs for past messages."
    )
    @discord.app_commands.describe(day="How far back do we go.")
    async def timemachine(self, ctx: commands.Context, *, day: int = -1):
        await ctx.typing()
        if 0 < day:
            async for message in ctx.channel.history(
                limit=1, before=datetime.now() - timedelta(days=day)
            ):
                return await ctx.reply(message.jump_url)
        elif -1 == day:
            async for message in ctx.channel.history(limit=1, after=ctx.channel.created_at):
                return await ctx.reply(message.jump_url)
        else:
            return await ctx.reply(t({
                "ja": "未来にはいけません。",
                "en": "I can't read messages that on the future."
            }, ctx))
        await ctx.reply(t({
            "ja": "過去にさかのぼりすぎました。",
            "en": "I was transported back in time to another dimension."
        }, ctx))

    ((TM_HELP := Cog.HelpCommand(timemachine))
        .merge_headline(
            ja="過去のメッセージのジャンプURLを表示します。",
            en=timemachine.description
        )
        .set_description(**TM_HELP.headline)
        .add_arg("day", "int", ("default", "-1"),
            ja="どのくらい遡るかの日数です。\n`-1`の場合は最初のメッセージです。",
            en="The number of days to go back how far.\nIf `-1`, it is the first message."))
    del TM_HELP

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or not isinstance(message.channel, discord.TextChannel) \
                or message.channel.topic is None:
            return

        for line in message.channel.topic.splitlines():
            if line.startswith("rt>autoPublish"):
                await message.publish()
                if len(line.split()) >= 1:
                    option = line.split()[0]
                    if option == "check":
                        await message.add_reaction("✅")

        if f"{TOPIC_PREFIX}thread" in message.channel.topic:
            if message.channel.slowmode_delay >= 10:
                await message.channel.create_thread(
                    name=message.content[:message.content.find("\n")]
                        if "\n" in message.content else message.content,
                    message=message
                )
            else:
                await message.channel.edit(slowmode_delay=10)

    @commands.command(
        description="Setting nsfw channel", fsparent=FSPARENT,
        aliases=("えっc", "r18")
    )
    @discord.app_commands.describe(channel="Text channel", nsfw="If you want to set nsfw, you should to do true")
    async def nsfw(self, ctx, nsfw: bool, channel: discord.TextChannel | None = None):
        ch = channel or ctx.channel
        await ch.edit(nsfw=nsfw)
        await ctx.reply("Ok")

    Cog.HelpCommand(nsfw) \
        .set_description(ja="nsfwチャンネルに設定します。", en=nsfw.description) \
        .merge_headline(ja="nsfwチャンネルを設定します。") \
        .add_arg(
            "nsfw", "bool",
            ja="nsfwを設定するかどうか",
            en="True or False"
        ) \
        .add_arg(
            "channel", "Optional",
            ja="設定したいテキストチャンネル",
            en="When you want to setting nsfw channel"
        )


async def setup(bot):
    await bot.add_cog(ServerManagement(bot))