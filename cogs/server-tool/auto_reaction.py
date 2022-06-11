# RT - Auto Reaction

from discord.ext import commands
import discord

from core import RT, Cog, t

from .__init__ import FSPARENT


class InputEmojiModal(discord.ui.Modal, title="Input emojis"):
    "絵文字の入力をしてもらうモーダルです。"

    emojis = discord.ui.TextInput(label="...", default="😂 🤣")

    def __init__(self, ctx: discord.Interaction, message: discord.Message, *args, **kwargs):
        self.message = message
        self.emojis.label = t({
            "ja": "空白分けした絵文字", "en": "String of emojis separated by spaces"
        }, ctx)
        super().__init__(*args, **kwargs)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # 絵文字を付ける
        await interaction.response.send_message("Now adding...", ephemeral=True)
        for emoji in str(self.emojis).split():
            await self.message.add_reaction(emoji)
        await interaction.edit_original_message(content="Ok")


COMMAND_NAME = "Auto Reaction"
class AutoReaction(Cog):
    def __init__(self, bot: RT):
        self.bot = bot

    async def cog_load(self):
        self.bot.tree.add_command(discord.app_commands.ContextMenu(
            name=COMMAND_NAME, callback=self.auto_reaction,
            type=discord.AppCommandType.message
        ))

    async def cog_unload(self):
        self.bot.tree.remove_command(COMMAND_NAME)

    @commands.Cog.listener()
    async def on_help_load(self):
        self.bot.help_.set_help(Cog.Help()
            .set_category(FSPARENT)
            .set_title(COMMAND_NAME)
            .set_description(
                ja=f"メッセージのアプリのコンテキストメニューにある`{COMMAND_NAME}`を実行することで、自動でメッセージにリアクションを付けることができます。",
                en=f"You can automatically add a reaction to a message by executing `{COMMAND_NAME}` in the context menu of the message's application."
            ))

    @discord.app_commands.checks.has_permissions(add_reactions=True)
    async def auto_reaction(self, interaction: discord.Interaction, message: discord.Message):
        # リアクションを付けます。
        await interaction.response.send_modal(InputEmojiModal(interaction, message))


async def setup(bot: RT) -> None:
    await bot.add_cog(AutoReaction(bot))