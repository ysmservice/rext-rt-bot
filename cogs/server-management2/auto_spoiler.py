# RT - AutoSpoiler

from re import findall

from discord.ext import commands
import discord

from core import RT

from rtutil.utils import webhook_send


class RemoveButton(discord.ui.View):
    "削除ボタンです。"

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__()

    @discord.ui.button(label="削除ボタン", style=discord.ButtonStyle.danger, emoji="🗑")
    async def remove_button(self, interaction: discord.Interaction, _):
        if self.user_id == interaction.user.id:
            await interaction.response.send_message(
                {
                    "ja": "削除します。", "en": "I'll delete this message."
                }, ephemeral=True
            )
            if interaction.message:
                await interaction.message.delete(delay=2.35)
        else:
            await interaction.response.send_message(
                {
                    "ja": "あなたはこのメッセージを削除できません。",
                    "en": "You can't delete this message."
                }, ephemeral=True
            )

class ChannelPluginGeneral(commands.Cog):

    URL_PATTERN = "https?://[\\w/:%#\\$&\\?\\(\\)~\\.=\\+\\-]+"

    def __init__(self, bot: RT):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not isinstance(message.channel, discord.TextChannel):
            return
        if not message.guild or message.author.discriminator == "0000":
            return

        if message.channel.topic:
            for cmd in message.channel.topic.splitlines():
                if cmd.startswith(("rt>asp", "rt>AutoSpoiler")):
                    # Auto Spoiler
                    content = message.clean_content

                    # 添付ファイルをスポイラーにする。
                    new = []
                    for attachment in message.attachments:
                        attachment.filename = f"SPOILER_{attachment.filename}"
                        new.append(await attachment.to_file())
                    # urlをスポイラーにする。
                    for url in findall(self.URL_PATTERN, content):
                        content = content.replace(url, f"||{url}||", 1)
                    # もしスポイラーワードが設定されているならそれもスポイラーにする。
                    for word in cmd.split()[1:]:
                        content = content.replace(word, f"||{word}||")
                    # Embedに画像が設定されているなら外してスポイラーを付けた画像URLをフィールドに入れて追加する。
                    e = False
                    for index in range(len(message.embeds)):
                        if message.embeds[index].image.url:
                            message.embeds[index].add_field(
                                name="この埋め込みに設定されている画像",
                                value=f"||{message.embeds[index].image.url}||"
                            )
                            message.embeds[index].set_image(url=None)
                            e = True

                    # 送信し直す。
                    if ((message.content and message.clean_content != content)
                            or message.attachments or (message.embeds and e)):
                        # 送信しなおす。
                        if message.reference:
                            content = f"返信先：{message.reference.jump_url}\n{content}"
                        await webhook_send(
                            message.channel, message.author, content=content,  # type: ignore
                            files=new, embeds=message.embeds,
                            username=message.author.display_name + " RT's Auto Spoiler",
                            avatar_url=message.author.display_avatar.url,
                            view=RemoveButton(message.author.id)
                        )
                        try:
                            await message.delete()
                        except (discord.NotFound, discord.Forbidden):
                            pass


def setup(bot):
    bot.add_cog(ChannelPluginGeneral(bot))
