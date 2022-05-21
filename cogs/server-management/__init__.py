# RT - Server Management

from datetime import datetime, timedelta

from discord.ext import commands
import discord

from core import RT, Cog, t

from rtlib.common.utils import code_block
from rtlib.common import dumps
from rtutil.collectors import make_google_url
from rtutil.utils import ContentData
from rtutil.views import TimeoutView


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
        await self.message.reply(
            t(dict(
                ja="{mention}により検索が行われました。\n{content}",
                en="The search was performed by {mention} command.\n{content}"
            ), interaction, mention=interaction.user.mention, content=self.content),
            allowed_mentions=discord.AllowedMentions.none()
        )


class ServerManagement(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self._CTX_MES_SEARCH = "Search"
        self._CTX_MES_GC = "Get content"
        self.bot.tree.add_command(discord.app_commands.ContextMenu(
            name=self._CTX_MES_SEARCH, callback=self.search,
            type=discord.AppCommandType.message
        ))
        self.bot.tree.add_command(discord.app_commands.ContextMenu(
            name=self._CTX_MES_GC, callback=self.get_embed,
            type=discord.AppCommandType.message
        ))

    async def cog_unload(self):
        self.bot.tree.remove_command(self._CTX_MES_SEARCH)
        self.bot.tree.remove_command(self._CTX_MES_GC)

    @commands.Cog.listener()
    async def on_help_load(self):
        self.bot.help_.set_help(Cog.Help()
            .set_title("Context Search")
            .set_headline(ja="お手軽検索", en="Easliy search")
            .set_description(
                ja="""検索したいメッセージのコンテキストメニューのアプリの`Search`を押すことで、Googleの検索のURLを作ります。
                「とは」が後ろについている場合はそれを消して検索をします。""",
                en="Create a Google search URL by pressing `Search` on the app in the context menu of the message you want to search."
            )
            .set_category(FSPARENT))
        self.bot.help_.set_help(Cog.Help()
            .set_title("Get content")
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

    async def get_embed(self, interaction: discord.Interaction, message: discord.Message):
        data = ContentData(content={}, author=message.author.id, json=True)
        if message.content:
            data["content"]["content"] = message.content
        if message.embeds:
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
        view.add_item(SearchResultShowButton(
            f"Search for this message: {make_google_url(content)}", message, label="みんなが見れるようにする。"
                if self.bot.search_language(interaction.guild_id, interaction.user.id)
                    == "ja"
                else "Show everyone"
        ))
        await interaction.response.send_message(
            getattr(view.children[0], "content"), ephemeral=True, view=view
        )

    @commands.command(
        aliases=("msgc", "メッセージカウント", "メッセージ数"), fsparent=FSPARENT,
        description="Count the number of messages in the channel up to 5,000."
    )
    @commands.cooldown(1, 600, commands.BucketType.channel)
    @discord.app_commands.describe(content="The characters that must be included in the message to be counted. If not specified, all are included.")
    async def messagecount(self, ctx: commands.Context, *, content: str | None = None):
        message = await ctx.reply(t({
            "ja": "数え中...", "en": "Counting..."
        }, ctx))
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


async def setup(bot):
    await bot.add_cog(ServerManagement(bot))