# RT - NickName Panel

from __future__ import annotations

from discord.ext import commands
import discord

from rtlib.common.json import loads

from rtutil.utils import is_json, replace_nl
from rtutil.content_data import ContentData
from rtutil.panel import extract_emojis

from core import Cog, RT, t

from data import NO_MORE_SETTING, FORBIDDEN

from .__init__ import FSPARENT
from .role import RolePanel


class NickNamePanelEventContext(Cog.EventContext):
    "ニックネームパネルのニックネームを設定した際のイベントコンテキストです。"

    member: discord.Member
    nickname: str


class NickNamePanelView(discord.ui.View):
    "ニックネームパネルのViewです。"

    def __init__(self, cog: NickNamePanel, *args, **kwargs):
        self.cog = cog
        super().__init__(*args, **kwargs)

    @discord.ui.select(placeholder="Set nickname", custom_id="nickpanel.select")
    async def select_nickname(self, interaction: discord.Interaction, select: discord.ui.Select):
        # ニックネームを設定します。
        assert isinstance(interaction.user, discord.Member)
        nickname = select.values[0]
        nickname = f"{interaction.user.display_name}{nickname[1:]}" \
            if nickname.startswith("+") else nickname
        error = None
        try:
            await interaction.user.edit(nick=nickname)
        except discord.Forbidden:
            await interaction.response.send_message(t(FORBIDDEN, interaction), ephemeral=True)
            error = FORBIDDEN
        else:
            await interaction.response.send_message("Ok", ephemeral=True)
        self.cog.bot.rtevent.dispatch("on_nickname_panel", NickNamePanelEventContext(
            self.cog.bot, interaction.guild, self.cog.detail_or(error), {
                "ja": "ニックネームパネル", "en": "Nickname Panel"
            }, self.cog.text_format({
                "ja": "対象：{name}\nニックネーム：{nickname}",
                "en": "Target: {name}\nNickname: {nickname}"
            }, name=self.cog.name_and_id(interaction.user), nickname=nickname),
            self.cog.nickname_panel, error, member=interaction.user, nickname=nickname
        ))


class NickNamePanel(Cog):
    "ニックネームパネルのコグです。"

    def __init__(self, bot: RT):
        self.bot = bot

    @commands.Cog.listener()
    async def on_setup(self):
        self.bot.add_view(NickNamePanelView(self, timeout=None))

    @commands.command(
        aliases=("nickpanel", "np", "ニックネームパネル", "ニックパネル", "にぱ"), fsparent=FSPARENT,
        description="Create a panel to change nicknames. You can create a panel for setting nicknames."
    )
    @discord.app_commands.describe(
        title="The title of the panel.", content="Nicknames separated by `<nl>`."
    )
    async def nickname_panel(self, ctx: commands.Context, title: str, *, content: str):
        if not isinstance(ctx.channel, discord.TextChannel):
            return await ctx.reply(t(dict(
                ja="このコマンドはテキストチャンネル限定です。",
                en="This command is limited to text channels."
            ), ctx))

        # もし`Get content`のコードなら内容をそっから取る。
        if is_json(content):
            data: ContentData = loads(content)
            content = data["content"]["embeds"][0]["description"]

        content = replace_nl(content)
        if len(nicknames := extract_emojis(content)) > 25:
            return await ctx.reply(t(NO_MORE_SETTING, ctx))

        # Viewを作る。
        view = NickNamePanelView(self, timeout=0)
        view.select_nickname.placeholder = t(dict(
            ja="ニックネームを設定する", en="Set nickname"
        ), ctx)
        embed = discord.Embed(title=title, description="", color=ctx.author.color)
        assert isinstance(embed.description, str)
        # 内容をViewと埋め込みに追加していく。
        for emoji, nickname in nicknames.items():
            raw = nickname
            if nickname.startswith("+"):
                nickname = nickname[1:]
            view.select_nickname.add_option(label=nickname, value=raw, description=t(dict(
                ja="あなたの名前の後ろにこれを付けます。",
                en="Add this string after your name."
            ), ctx) if raw[0] == "+" else t(dict(
                ja="ニックネームを変更します。", en="Change nickname."
            ), ctx), emoji=emoji)
            embed.description += f"{emoji} {nickname}\n"
        embed.description = embed.description[:-1]
        # ブランド付けをする。
        embed.set_footer(text=t(dict(ja="RTのニックネームパネル", en="RT's Nickname Panel"), ctx))

        assert isinstance(self.bot.cogs["RolePanel"], RolePanel)
        await self.bot.cogs["RolePanel"].reply(ctx, embed=embed, view=view)

    (Cog.HelpCommand(nickname_panel)
        .merge_description("headline", ja="ニックネームパネルを作ります。ニックネームを設定するためのパネルを作れます。")
        .add_arg("title", "str",
            ja="ニックネームパネルに設定するタイトルです。", en="The title of the panel.")
        .add_arg("content", "str",
            ja="""改行か`<nl>`または`<改行>`で区切ったニックネームです。
            ニックネームの最初に`+`を付けることで、丸ごとニックネームを変更するのではなく、ニックネームを名前に後付けするようにすることができます。""",
            en="""A nickname separated by a newline or `<nl>` or `<nl>`.
            You can add a `+` at the beginning of the nickname to make the nickname follow the name instead of changing the nickname in its entirety.""")
        .set_extra("Notes",
            ja="""`Get content`を使って取得したコードで他のパネルの内容をコピーすることができます。
            また、`rt!`形式でのコマンドをニックネームパネルに返信して実行した場合、そのパネルを新しい内容に上書きすることができます。""",
            en="""You can copy the contents of other panels with the code obtained using `Get content`.
            Also, if you execute a command in the form `rt!` in reply to a nick panel, you can overwrite that panel with the new content."""))


async def setup(bot: RT) -> None:
    await bot.add_cog(NickNamePanel(bot))