# RT - Translator

from discord.ext.commands import command, Context
import discord

from jishaku.functools import executor_function

from deep_translator.exceptions import LanguageNotSupportedException
from deep_translator import GoogleTranslator

from rtlib import Cog, RT


class Translator(Cog):
    def __init__(self, bot: RT):
        self.bot = bot

    @executor_function
    def translate(self, target: str, content: str) -> str:
        return GoogleTranslator(target=target).translate(content)

    @command("translate", description="Translation.", aliases=("trans", "翻訳"))
    @discord.app_commands.describe(
        language="The language code of the target language.",
        content="The text to be translated."
    )
    async def translate_(self, ctx: Context, language: str, *, content: str):
        await ctx.trigger_typing()

        if language == "auto":
            # もし自動で翻訳先を判別するなら英文字が多いなら日本語にしてそれ以外は英語にする。
            language = "ja" if (
                sum(64 < ord(char) < 123 for char in content)
                >= len(content) / 2
            ) else "en"

        try:
            await ctx.reply(
                embed=Cog.Embed(
                    title=Cog.t({"ja": "翻訳", "en": "Translation"}, ctx),
                    description=await self.translate(language, content)
                ).set_footer(
                    text="Powered by Google Translate",
                    icon_url="http://tasuren.syanari.com/RT/GoogleTranslate.png"
                )
            )
        except LanguageNotSupportedException:
            await ctx.reply(Cog.t(dict(
                ja="その言語は対応していません。", en="That language is not supported."
            ), ctx))

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if not isinstance(message.channel, discord.TextChannel) \
                or message.channel.topic is None:
            return 

        for line in message.channel.topic.splitlines():
            if line.startswith("rt>tran "):
                _, target = line.split()
                await self.translate_(
                    await self.bot.get_context(message), target,
                    content=message.clean_content
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