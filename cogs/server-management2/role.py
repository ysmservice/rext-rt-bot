# RT - Role Panel

from __future__ import annotations

from discord.ext import commands
import discord

from core import Cog, RT, t

from rtlib.common.json import loads

from rtutil.utils import (
    artificially_send, adjust_min_max, replace_nl, is_json, fetch_webhook,
    edit_reference
)
from rtutil.content_data import ContentData
from rtutil.panel import extract_emojis

from data import FORBIDDEN, NO_MORE_SETTING

from .__init__ import FSPARENT


class RolePanelEventContext(Cog.EventContext):
    "役職パネルのイベントコンテキストです。"

    add: set[discord.Role]
    remove: set[discord.Role]


class RolePanelView(discord.ui.View):
    "役職パネルのViewです。"

    def __init__(self, cog: RolePanel, *args, **kwargs):
        self.cog = cog
        super().__init__(*args, **kwargs)

    def extract_description(self, interaction: discord.Interaction) -> str:
        # 説明を取り出します。
        assert interaction.message is not None \
            and interaction.message.embeds[0].description is not None
        return interaction.message.embeds[0].description

    @discord.ui.select(custom_id="role_panel.add_roles")
    async def add_roles(self, interaction: discord.Interaction, select: discord.ui.Select):
        # 役職を付与する。
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        description = self.extract_description(interaction)

        # 付与するロールのリストを作る。
        roles, remove_roles, error = set(), set(), None
        for id_ in (selected := set(map(int, select.values))):
            role = interaction.guild.get_role(id_)

            if role is None:
                await interaction.response.send_message(t(
                    error := self.cog.text_format({
                        "ja": "ロールが見つかりませんでした：{id_}",
                        "en": "Role not found: {id_}"
                    }, id_=id_), interaction
                ), ephemeral=True)
                break

            if interaction.user.get_role(id_) is None:
                roles.add(role)

        # ロールの処理を行う。
        try:
            if not error:
                # 削除するロールのリストを作り削除を行う。
                if remove_roles := set(role for role in filter(
                    lambda role: role.id not in selected and str(role.id) in description,
                    interaction.user.roles
                )):
                    await interaction.user.remove_roles(*remove_roles)
                # ロールの付与を行う。
                if roles:
                    await interaction.user.add_roles(*roles)
        except discord.Forbidden:
            await interaction.response.send_message(t(dict(
                ja="権限がないためロールの処理に失敗しました。",
                en="Role processing failed due to lack of permissions."
            ), interaction), ephemeral=True)
            error = FORBIDDEN
        else:
            await interaction.response.send_message("Ok", ephemeral=True)

        self.cog.bot.rtevent.dispatch("on_role_panel", RolePanelEventContext(
            self.cog.bot, interaction.guild, self.cog.detail_or(error), {
                "ja": "役職パネル", "en": "Role Panel"
            }, self.cog.text_format({
                "ja": "対象：{name}\nロール：{roles}", "en": "Target: {name}\nRoles: {roles}"
            }, name=self.cog.name_and_id(interaction.user), roles=", ".join(
                self.cog.name_and_id(role) for role in roles
            )), self.cog.role, error, add=roles, remove=remove_roles
        ))

    @discord.ui.button(
        custom_id="role_panel.remove_roles",
        style=discord.ButtonStyle.danger,
        emoji="🗑"
    )
    async def remove_roles(self, interaction: discord.Interaction, _):
        # 役職を削除する。
        description = self.extract_description(interaction)
        assert isinstance(interaction.user, discord.Member)
        if roles := set(role for role in interaction.user.roles if str(role.id) in description):
            await interaction.user.remove_roles(*roles)
        await interaction.response.send_message("Ok", ephemeral=True)


class RolePanel(Cog):
    "役職パネルのコグです。"

    def __init__(self, bot: RT):
        self.bot = bot

    @commands.Cog.listener()
    async def on_setup(self):
        self.bot.add_view(RolePanelView(self, timeout=None))

    @commands.command(
        aliases=("rp", "役職パネル", "ロールパネル", "やぱ", "ろぱ"), fsparent=FSPARENT,
        description="Create a role panel."
    )
    @discord.app_commands.rename(min_="min", max_="max")
    @discord.app_commands.describe(
        min_=(_d_mi := "The minimum number of roles that can be added."),
        max_=(_d_ma := "The maximum number of roles that can be added."),
        title=(_d_t := "Title of role panel."),
        content="Enter the name or ID of the role to be included in the role panel, separated by `<nl>`.",
    )
    @commands.has_guild_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.channel)
    async def role(
        self, ctx: commands.Context, min_: int = -1,  max_: int = -1,
        title: str = "Role Panel", *, content: str
    ):
        # テキストチャンネル以外は除外する。
        if not isinstance(ctx.channel, discord.TextChannel):
            raise Cog.reply_error.BadRequest({
                "ja": "テキストチャンネルである必要があります。",
                "en": "Must be a text channel."
            })

        # `Get content`の場合は中身を取り出す。
        if is_json(content):
            data: ContentData = loads(content)
            content = data["content"]["embeds"][0]["description"]

        content = replace_nl(content)
        if (length := len(roles := extract_emojis(content))) > 25:
            return await ctx.reply(t(NO_MORE_SETTING, ctx))

        # Viewの設定を行う。
        view = RolePanelView(self, timeout=0)
        view.add_roles.min_values, view.add_roles.max_values = adjust_min_max(
            length, min_, max_
        )
        # ロールをオプションとして全て追加する。
        for emoji, role in (roles := [
            (emoji, await commands.RoleConverter().convert(ctx, target.strip()))
            for emoji, target in roles.items()
        ]):
            view.add_roles.add_option(label=role.name, value=str(role.id), emoji=emoji)
        view.add_roles.placeholder = t(dict(ja="ロールを設定する", en="Set roles"), ctx)
        view.remove_roles.label = t(dict(ja="ロールをリセットする", en="Reset roles"), ctx)

        # 埋め込みを作る。
        await self.reply(ctx, embed=discord.Embed(
            title=title, description="\n".join(
                f"{emoji} {role.mention}" for emoji, role in roles
            ), color=ctx.author.color
        ).set_footer(text=t(dict(
            ja="RTの役職パネル", en="RT's Role Panel"
        ), ctx)), view=view)

    async def reply(self, ctx: commands.Context, **kwargs):
        "色々な処理をして返信をします。"
        if ctx.message.reference is None:
            # 役職パネルを送信する。
            assert isinstance(ctx.author, discord.Member) \
                and isinstance(ctx.channel, discord.TextChannel | discord.Thread)
            await artificially_send(ctx.channel, ctx.author, **kwargs)
        else:
            # 返信された際は返信先の役職パネルを更新する。
            reply = await edit_reference(self.bot, ctx.message, **kwargs)
            if isinstance(reply, str):
                return await ctx.reply(reply)
        if ctx.interaction is not None:
            await ctx.interaction.response.send_message("Ok", ephemeral=True)

    (Cog.HelpCommand(role)
        .merge_description("headline", ja="役職パネルを作ります。")
        .add_arg("min", "int", ("default", "-1"),
            ja="設定できるロールの最低個数です。", en=_d_mi)
        .add_arg("max", "int", ("default", "-1"),
            ja="設定できるロールの最大個数です。", en=_d_ma)
        .add_arg("title", "str", ("default", "Role Panel"),
            ja="役職パネルのタイトルです。", en=_d_t)
        .add_arg("content", "str",
            ja="""改行または`<nl>`か`<改行>`で分けた役職の名前かIDです。
            `Get content`で取得したコードをこの引数に入れることも可能です。
            その場合はコードに埋め込みの説明欄が含まれている必要があります。
            これは、役職パネルの内容を簡単にコピーするために使用しましょう。""",
            en="""The name or ID of the role, separated by a newline or `<nl>` or `<nl>`.
            It is also possible to put code obtained with `Get content` into this argument.
            In that case, the code must contain an embedded description field.
            This should be used to easily copy the content of the position panel.""")
        .set_extra("Notes",
            ja="`rt!`形式のコマンドを役職パネルのメッセージに返信して実行すると、その役職パネルの内容を上書きすることができます。",
            en="Executing a command of the form `rt!` in reply to a role panel message will overwrite the contents of that role panel."))
    del _d_mi, _d_ma, _d_t


async def setup(bot: RT) -> None:
    await bot.add_cog(RolePanel(bot))