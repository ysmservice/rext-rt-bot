# RT - Free Channel

from __future__ import annotations

from typing import Literal

from dataclasses import dataclass
from time import time

from discord.ext import commands
import discord

from core import Cog, RT, t

from rtlib.common.cacher import Cacher

from .__init__ import FSPARENT


class FreeChannelPanelView(discord.ui.View):
    "フリーチャンネルのパネルのViewです。\nボタン等はこれには未実装で、実際には別のものを使います。"

    def __init__(self, cog: FreeChannel, *args, **kwargs):
        kwargs.setdefault("timeout", 0)
        self.cog = cog
        super().__init__(*args, **kwargs)

    async def create_channel(
        self, mode: Literal["text", "voice"],
        interaction: discord.Interaction
    ):
        "チャンネルを作成します。"
        assert interaction.guild is not None \
            and isinstance(interaction.channel, discord.TextChannel) \
            and interaction.message is not None

        # 情報を取り出す。
        max_, editable, role_id = interaction.message.content.split("_")
        max_ = int(max_)

        # クールダウンを有効にする。
        key = (mode, interaction.guild.id, interaction.user.id)
        if (now := self.cog.created.get(key, 0)) >= max_:
            return await interaction.response.send_message(t(dict(
                ja="やりすぎです。\n十二時間程待機してください。",
                en="It is too many requests.\nPlease wait for about twelve hours."
            ), interaction), ephemeral=True)
        else:
            self.cog.created[key] = now + 1

        # 下準備をする。
        role_id, editable = int(role_id), bool(int(editable))

        # 権限設定を作る。
        overwrites = {}
        if role_id != 0:
            if (role := interaction.guild.get_role(role_id)):
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, manage_channels=True
                )
            overwrites[interaction.user] = discord.PermissionOverwrite(view_channel=True)
            overwrites[interaction.guild.default_role] = \
                discord.PermissionOverwrite(view_channel=False)
        if editable:
            overwrites[interaction.user] = discord.PermissionOverwrite(view_channel=True, manage_channels=True)

        # チャンネルを作成する。
        channel: discord.TextChannel | discord.VoiceChannel = await getattr(
            interaction.channel.category or interaction.guild, f"create_{mode}_channel"
        )(
            f"{interaction.user.display_name}-{int(time())}", reason=t(dict(
                ja="フリーチャンネル", en="FreeChannel"
            ), interaction.guild), overwrites=overwrites
        )
        await interaction.response.send_message(t(dict(
            ja="チャンネルを作成しました：{mention}", en="I created your channel: {mention}"
        ), interaction, mention=channel.mention), ephemeral=True)
class FreeChannelPanelTextView(FreeChannelPanelView):
    @discord.ui.button(emoji="📝", custom_id="FreeChannelPanelText")
    async def text(self, interaction: discord.Interaction, _):
        await self.create_channel("text", interaction)
class FreeChannelPanelVoiceView(FreeChannelPanelView):
    @discord.ui.button(emoji="📞", custom_id="FreeChannelPanelVoice")
    async def voice(self, interaction: discord.Interaction, _):
        await self.create_channel("voice", interaction)
class FreeChannelPanelAllView(FreeChannelPanelTextView, FreeChannelPanelVoiceView): ...


@dataclass
class Views:
    "フリーチャンネルのパネルのViewを格納するためのクラスです。"

    voice: FreeChannelPanelVoiceView
    text: FreeChannelPanelTextView
    all: FreeChannelPanelAllView


class FreeChannel(Cog):
    "フリーチャンネルのコグです。"

    def __init__(self, bot: RT):
        self.bot = bot
        self.created: Cacher[tuple[str, int, int], int] = self.bot.cachers.acquire(43200)
        self.views = Views(
            FreeChannelPanelVoiceView(self, timeout=None),
            FreeChannelPanelTextView(self, timeout=None),
            FreeChannelPanelAllView(self, timeout=None)
        )

    @commands.Cog.listener()
    async def on_setup(self):
        for view in map(lambda key: getattr(self.views, key), self.views.__annotations__.keys()):
            self.bot.add_view(view)

    @commands.command(
        aliases=("fch", "フリーチャンネル", "フリーチャ", "個人チャット", "個チャ"), fsparent=FSPARENT,
        description="Create a panel where everyone is free to create their own channels."
    )
    @discord.app_commands.rename(max_="max")
    @discord.app_commands.describe(
        mode="Channel creation panel mode.",
        editable="Whether the channel creator can change the channel name, etc.",
        max_="It is how many channels can be created every twelve hours.",
        role="The role available to view the channel when making it a secret channel. Unspecified, etc. will not be a secret channel.",
        content="Message content of the panel. Unspecified will be generated automatically."
    )
    @commands.cooldown(1, 15, commands.BucketType.category)
    @commands.has_guild_permissions(manage_channels=True, manage_roles=True)
    async def free_channel(
        self, ctx: commands.Context, mode: Literal["all", "text", "voice", "ticket"],
        editable: bool, max_: int = 5, role: discord.Role | None = None, *, content: str = ""
    ):
        is_ticket = mode == "ticket"
        if is_ticket:
            mode = "text"
        # Viewを用意する。
        view: discord.ui.View = getattr(self.views, mode).__class__(self, timeout=0)
        for mode, text in filter(lambda data: hasattr(view, data[0]), (
            ("text", dict(ja="テキストチャンネル", en="Text Channel")),
            ("voice", dict(ja="ボイスチャンネル", en="Voice Channel"))
        ) + (
            (("text", dict(ja="チャンネルを作る", en="Create your channel")),)
            if is_ticket else ()
        )):
            getattr(view, mode).label = t(text, ctx)
        if is_ticket:
            # チケットモードの時は特別に絵文字を変更する。
            getattr(view, "text").emoji = "🎫"
        # パネルを送信する。
        await ctx.message.channel.send(f"{max_}_{int(editable)}_{getattr(role, 'id', 0)}",
        embed=self.embed(description=content or t(dict(
            ja="チケット作成パネルです。\n下のボタンからチャンネルを作成することができます。",
            en="Ticket creation panel.\nYou can create a channel by pressing the an button."
        ), ctx) if is_ticket else t(dict(
            ja="フリーチャンネル作成パネルです。\nボタンを押すことでチャンネルを作成することができます。",
            en="Free channel creation panel.\nYou can create a channel by pressing the an button."
        ), ctx)), view=view)
        if ctx.interaction is not None:
            await ctx.interaction.response.send_message("Ok", ephemeral=True)

    (Cog.HelpCommand(free_channel)
        .merge_headline(ja="チャンネルを作成するパネルを作ります。")
        .merge_description(ja="チャンネルを作成するパネルを作ります。")
        .add_arg("mode", "Choice",
            ja="""チャンネル作成のモードです。
            `all` テキストチャンネルとボイスチャンネルの作成ボタン
            `text` テキストチャンネルだけの作成ボタン
            `voice` ボイスチャンネルだけの作成ボタン
            `ticket` テキストチャンネルだけの作成ボタン(チケットパネル)""",
            en="""Channel creation mode.
            `all` buttons for creating text and voice channels
            `text` Button to create text channel only.
            `voice` button to create voice channel only
            `ticket` button to create only text channel (ticket panel)""")
        .add_arg("editable", "bool",
            ja="作成者がチャンネルの削除や名前の変更等を行えるようにするかどうかです。",
            en="Whether or not the creator should be able to delete, rename, etc. the channel.")
        .add_arg("max", "int", ("default", "5"),
            ja="12時間に何回チャンネルの作成を行うことができるかです。",
            en="It is the number of times a channel can be created in a 12-hour period.")
        .add_arg("role", "Role", "Optional",
            ja="""作成されるチャンネルを見るために必要なロールです。
            これを指定した場合はシークレットチャンネルが作られるようになりますが、指定しない場合は誰でも見れるチャンネルとなります。""",
            en="""This is the role required to view the channels that will be created.
            If this is specified, a secret channel will be created; if not specified, the channel will be available to everyone.""")
        .add_arg("content", "str", "Optional",
            ja="作成されるパネルに入れる文字列です。", en="The string to be included in the panel to be created."))


async def setup(bot: RT) -> None:
    await bot.add_cog(FreeChannel(bot))