# RT - Expander

from __future__ import annotations

from typing import Literal
from collections.abc import Iterator

from enum import Enum
from re import findall

from discord.ext import commands
import discord

from core import RT, Cog, t, DatabaseManager, cursor

from rtlib.common.cacher import Cacher
from rtutil.utils import unwrap_or, artificially_send

from .__init__ import FSPARENT


class Method(Enum):
    "メッセージリンク展開をどのようにするかです。"

    WEBHOOK = 1
    NOWEBHOOK = 2
    NONE = 4 # 何もしない


class DataManager(DatabaseManager):
    def __init__(self, cog: Expander):
        self.cog = cog
        self.pool = self.cog.bot.pool
        self.caches: Cacher[int, Method] = self.cog.bot.cachers.acquire(3600.0)

    async def prepare_table(self) -> None:
        "テーブルを作ります。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS Expander (
                GuildId BIGINT PRIMARY KEY NOT NULL,
                Method ENUM("WEBHOOK", "NOWEBHOOK", "NONE")
            );"""
        )

    async def read(self, guild_id: int, **_) -> Method:
        "設定を読み込みます。"
        if guild_id not in self.caches:
            await cursor.execute(
                "SELECT Method FROM Expander WHERE GuildId = %s;",
                (guild_id,)
            )
            self.caches[guild_id] = getattr(Method, row[0]) \
                if (row := await cursor.fetchone()) else Method.WEBHOOK
        return self.caches[guild_id]

    async def write(self, guild_id: int, method: Method) -> None:
        "設定を書き込みます。"
        await cursor.execute(
            """INSERT INTO Expander VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE Method = %s;""",
            (guild_id, method.name, method.name)
        )
        self.caches[guild_id] = method

    async def clean(self) -> None:
        "お掃除をします。"
        await self.cog.bot.clean(cursor, "Expander", "GuildId")


PATTERN =  (
    "https://(ptb.|canary.)?discord(app)?.com/channels/"
    "(?P<guild>[0-9]{18})/(?P<channel>[0-9]{18})/(?P<message>[0-9]{18})"
)
def expand(content: str) -> Iterator[tuple[int, int, int]]:
    "渡された文字列にあるメッセージリンクからIDを取り出し、ギルドIDとチャンネルIDとメッセージIDのタプルを返すイテレーターを返します。"
    for data in findall(PATTERN, content):
        try:
            _, _, guild_id, channel_id, message_id = data
        except ValueError:
            ...
        else:
            yield tuple(map(int, (guild_id, channel_id, message_id))) # type: ignore


class Expander(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)
        self.sent: Cacher[tuple[int, int], bool] = self.bot.cachers.acquire(10.0)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.Cog.listener()
    async def on_message_noprefix(self, message: discord.Message):
        if not message.content or message.author.bot or message.guild is None \
                or not isinstance(message.channel, discord.TextChannel | discord.Thread):
            return

        # キャッシュを作ったりする。
        data = await self.data.read(message.guild.id)
        if data == Method.NONE:
            return

        # メッセージリンクの展開を行う。
        embeds: list[discord.Embed] = []
        for guild_id, channel_id, target_id in expand(message.content):
            if self.sent.get((message.guild.id, target_id), False):
                continue
            assert message.guild is not None
            if guild_id == message.guild.id:
                # リンク先のオブジェクトを取得する。
                if (channel := message.guild.get_channel(channel_id)) is None \
                        or not isinstance(
                            channel, discord.Thread | discord.TextChannel
                        ) or (target := await channel.fetch_message(target_id)) is None:
                    continue
                self.sent[(message.channel.id, target_id)] = True
                embeds.append(discord.Embed(
                    description=target.content,
                    color=target.author.color
                ).set_author(
                    name=target.author.display_name,
                    icon_url=unwrap_or(target.author.display_avatar, "url", "")
                ))
                # もし画像がメッセージに設定されているのなら画像を追加する。
                if target.attachments:
                    embeds[-1].set_image(url=target.attachments[0].url)
                if target.embeds:
                    embeds.extend(target.embeds)

        # 展開したものを送信する。
        if embeds:
            if data == Method.WEBHOOK:
                await artificially_send(
                    message.channel, message.author, message.clean_content, # type: ignore
                    embeds=embeds[:5]
                )
                await message.delete()
            else:
                await message.reply(
                    embeds=embeds[:5], allowed_mentions=discord.AllowedMentions.none()
                )

    @commands.command(
        aliases=("展開", "メッセージリンク", "expr"), fsparent=FSPARENT,
        description="Message Link Expansion Settings"
    )
    @commands.guild_only()
    @discord.app_commands.describe(
        mode="This is how RT will display the link. If blank, the current setting will be displayed."
    )
    async def expansion(
        self, ctx: commands.Context, *,
        mode: Literal["webhook", "nowebhook", "none"] | None = None
    ):
        await ctx.typing()
        assert ctx.guild is not None
        if mode is None:
            await ctx.reply(t(dict(
                ja="現在の設定：`{data}`", en="Current setting: `{data}`"
            ), ctx, data=(await self.data.read(ctx.guild.id)).name))
        else:
            await self.data.write(ctx.guild.id, getattr(Method, mode.upper()))
            await ctx.reply("Ok")

    (Cog.HelpCommand(expansion)
        .merge_headline(
            ja="メッセージリンク展開の設定"
        )
        .set_description(
            ja="""メッセージリンクの展開の設定をします。
                この機能はデフォルトで有効です。
                メッセージリンクの展開というのは、メッセージのURLが送信された際に、そのURL先のメッセージの内容を表示するというものです。""",
            en="""Configure settings for message link expansion.
                This feature is enabled by default.
                Message link expansion means that when a message URL is sent, the content of the message at that URL is displayed."""
        )
        .add_arg("mode", "Choice", "Optional",
            ja="""どのように展開を行うかです。
                `webhook`: Webhookというものを使い引用のように表示します。
                    この場合メッセージが編集できなくなります。
                    デフォルトはこれになっています。
                `nowebhook`: 普通の送信で表示します。
                `none`: メッセージリンク展開を無効にします。
                もしこの引数を省略した場合現在の設定が表示されます。""",
            en="""Here's how to do the expansion.
                `webhook`: Use something called a webhook and display it as shown in the quote.
                    In this case, the message cannot be edited.
                    This is the default.
                `nowebhook`: display as a normal send.
                `none`: Disable message link expansion.
                If this argument is omitted, the current settings are displayed."""))


async def setup(bot):
    await bot.add_cog(Expander(bot))