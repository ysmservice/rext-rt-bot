# RT - Server Management

from discord.ext import commands
import discord

from core import RT, Cog, t

from rtutil.collectors import make_google_url
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
        self.bot.tree.remove_command("search")
        self.bot.tree.add_command(discord.app_commands.ContextMenu(
            name="Search", callback=self.search,
            type=discord.AppCommandType.message
        ))

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
            .set_title("autoPublish")
            .set_category(FSPARENT)
            .set_headline(ja="自動公開", en="Auto publish on news channel")
            .set_description(
                ja="""自動でニュースチャンネルのメッセージを公開します。
                    ニュースチャンネルのトピックに`rt>autoPublish`と入れることでできます。""",
                en="""Automatically publish messages on news channels.
                    You can do this by putting `rt>autoPublish` in the news channel topic."""
            ))

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