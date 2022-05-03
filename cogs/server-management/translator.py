# RT - Translator

from discord.ext import commands
import discord

from discord.ext.fslash import Context

from jishaku.functools import executor_function

from deep_translator.exceptions import LanguageNotSupportedException
from deep_translator import GoogleTranslator

from core.utils import quick_invoke_command
from core import Cog, RT, t


class Translator(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.bot.tree.remove_command("Translate")
        self.bot.tree.add_command(discord.app_commands.ContextMenu(
            name="Translate", callback=self.translate_from_context_menu,
            type=discord.AppCommandType.message
        ))

    @executor_function
    def translate(self, target: str, content: str) -> str:
        return GoogleTranslator(target=target).translate(content)

    FSPARENT = Cog.get_fsparent(__init__)

    @commands.command(
        "translate", description="Translation.",
        aliases=("trans", "翻訳"), fsparent=FSPARENT
    )
    @discord.app_commands.describe(
        language="The language code of the target language.",
        content="The text to be translated."
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def translate_(self, ctx: commands.Context, language: str, *, content: str):
        await ctx.typing()

        if language == "auto":
            # もし自動で翻訳先を判別するなら英文字が多いなら日本語にしてそれ以外は英語にする。
            language = "ja" if (
                sum(64 < ord(char) < 123 for char in content)
                >= len(content) / 2
            ) else "en"

        try:
            await ctx.reply(
                embed=Cog.Embed(
                    title=t({"ja": "翻訳", "en": "Translation"}, ctx),
                    description=await self.translate(language, content)
                ).set_footer(
                    text="Powered by Google Translate",
                    icon_url="http://tasuren.syanari.com/RT/GoogleTranslate.png"
                )
            )
        except LanguageNotSupportedException:
            await ctx.reply(t(dict(
                ja="その言語は対応していません。", en="That language is not supported."
            ), ctx))

    async def translate_from_context_menu(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        if message.content:
            await quick_invoke_command(
                self.bot, self.translate_, Context(interaction, {}, self.translate_, self.bot), # type: ignore
                kwargs={"language": "auto", "content": message.clean_content}
            )
        else:
            await interaction.response.send_message(t(dict(
                ja="メッセージ内容が空なので翻訳できませんでした。",
                en="The message content was empty and could not be translated."
            ), interaction))

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if not isinstance(message.channel, discord.TextChannel) \
                or message.channel.topic is None or not message.content \
                or message.author.id == self.bot.application_id:
            return

        for line in message.channel.topic.splitlines():
            if line.startswith(("rt>trans ", "rt>translate ")):
                _, target = line.split()
                await quick_invoke_command(
                    self.bot, self.translate_, message, "content",
                    kwargs={"language": target, "content": message.clean_content}
                )
                break

    (Cog.HelpCommand(translate_)
        .set_description(ja="翻訳をします。", en="Do translation.")
        .update_headline(ja="翻訳をします。")
        .add_arg("language", "str",
            ja="翻訳先の言語コードです。\n下にある`メモ`に使用可能だと思われているコードが書いてあります。",
            en="The language code of the language you are translating to.\nThe `Notes` below lists the possible language codes.")
        .add_arg("content", "str", ja="翻訳する文章です。", en="The text to be translated.")
        .set_extra("Notes", ja="""言語コード：
        ```
        自動\tauto
        日本語\tja
        英語\ten
        中国語(簡体字)\tzh-CN
        中国語(繁体字)\tzh-TW
        韓国語\tko
        アラビア語\tar
        ```""", en="""Language Code:
        ```
        Automatic\tauto
        Japanese\tja
        English\ten
        Chinese(Simplified)\tzh-CN
        Chinese(traditional)\tzh-TW
        Korean\tko
        Arabic(アラビア語)`\tar
        Arabic\tar
        ```"""))


async def setup(bot):
    await bot.add_cog(Translator(bot))