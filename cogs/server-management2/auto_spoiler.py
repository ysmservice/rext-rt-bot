# RT - AutoSpoiler

from re import findall

from discord.ext import commands
import discord

from core import RT, t, Cog

from rtutil.utils import webhook_send

from data import MESSAGE_NOTFOUND, FORBIDDEN

from .__init__ import FSPARENT


class RemoveButton(discord.ui.View):
    "削除ボタンです。"

    def __init__(self, member: discord.Member):
        self.author = member
        super().__init__()

    @discord.ui.button(label="削除ボタン", style=discord.ButtonStyle.danger, emoji="🗑")
    async def remove_button(self, interaction: discord.Interaction, _):
        if self.author.id == interaction.user.id:
            await interaction.response.send_message(t({
                "ja": "削除します。", "en": "I'll delete this message."
            }, self.author), ephemeral=True)
            if interaction.message:
                await interaction.message.delete(delay=2.35)
        else:
            await interaction.response.send_message(t({
                "ja": "あなたはこのメッセージを削除できません。",
                "en": "You can't delete this message."
            }, self.author), ephemeral=True)


class AutoSpolierEventContext(Cog.EventContext):
    "自動スポイラーのイベントコンテキストです。"
    channel: discord.TextChannel | None
    member: discord.Member | None


class AutoSpoiler(Cog):
    "自動スポイラーのコグです。"

    URL_PATTERN = "https?://[\\w/:%#\\$&\\?\\(\\)~\\.=\\+\\-]+"

    def __init__(self, bot: RT):
        self.bot = bot

    @commands.Cog.listener()
    async def on_help_load(self):
        self.bot.help_.set_help((help_ := Cog.Help())
            .set_category(FSPARENT)
            .set_headline(
                ja="自動で画像にスポイラーを設定します。",
                en="Automacially set spoiler to images."
            )
            .set_title("Auto Spoiler")
            .set_description(
                ja="{}\n{}".format(help_.headline["ja"],
                    "この機能を使いたいチャンネルのtopicに`rt>asp`を入れてください。"
                    "\nまた、`rt>asp`の後にスペースをあけて単語を入力するとその単語もスポイラーされます。"),
                en="{}\n{}".format(help_.headline["en"],
                    "Please add `rt>asp` to the topic of the channel you want to use this function."
                    "\nAfter adding `rt>asp` and a space, you can input a word to spoiler it.")
            )
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (not isinstance(message.channel, discord.TextChannel)
                or not isinstance(message.author, discord.Member)
                or not message.guild or message.author.discriminator == "0000"
                or not message.channel.topic):
            return

        for cmd in message.channel.topic.splitlines():
            if not cmd.startswith(("rt>asp", "rt>AutoSpoiler")):
                continue

            # Auto Spoiler
            is_replaced = False
            # 添付ファイルをスポイラーにする。
            new = []
            for attachment in message.attachments:
                new.append(await attachment.to_file(
                    filename=f"SPOILER_{attachment.filename}", spoiler=True
                ))
                is_replaced = True

            # urlをスポイラーにする。
            for url in findall(self.URL_PATTERN, message.content):
                message.content = message.content.replace(url, f"||{url}||", 1)
                is_replaced = True

            # もしスポイラーワードが設定されているならそれもスポイラーにする。
            for word in cmd.split()[1:]:
                if word in message.content:
                    message.content = message.content.replace(word, f"||{word}||")
                    is_replaced = True

            # Embedに画像が設定されているなら外してスポイラーを付けた画像URLをフィールドに入れて追加する。
            for index in range(len(message.embeds)):
                if message.embeds[index].image.url:
                    message.embeds[index].add_field(
                        name="この埋め込みに設定されている画像",
                        value=f"||{message.embeds[index].image.url}||"
                    )
                    message.embeds[index].set_image(url=None)
                    is_replaced = True

            if not is_replaced:
                return

            # 送信しなおす。
            if message.reference:
                message.content = f"返信先：{message.reference.jump_url}\n{message.content}"
            error = None
            await webhook_send(
                message.channel, message.author, content=message.content,
                files=new, embeds=message.embeds,
                username=message.author.display_name + " RT Auto Spoiler",
                avatar_url=message.author.display_avatar.url,
                view=RemoveButton(message.author)
            )
            try:
                await message.delete()
            except discord.NotFound:
                error = MESSAGE_NOTFOUND
            except discord.Forbidden:
                error = FORBIDDEN
            self.bot.rtevent.dispatch("on_global_ban_member", AutoSpolierEventContext(
                self.bot, message.guild, self.detail_or(error),
                {"ja": "自動スポイラー", "en": "Auto Spoiler"}, {
                    "ja": f"ユーザー:{Cog.mention_and_id(message.author)}",
                    "en": f"User: {Cog.mention_and_id(message.author)}"
                }, ("AutoSpoiler", "server-management2"),
                channel=message.channel, member=message.author
            ))


async def setup(bot: RT) -> None:
    await bot.add_cog(AutoSpoiler(bot))
