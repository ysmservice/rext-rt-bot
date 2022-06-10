# RT - Role Panel

from __future__ import annotations

from discord.ext import commands
import discord

from core import Cog, RT, t

from rtutil.utils import artificially_send, adjust_min_max, replace_nl
from rtutil.panel import extract_emojis

from data import FORBIDDEN

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

    @discord.ui.select(custom_id="role_panel.add_roles")
    async def add_roles(self, interaction: discord.Interaction, select: discord.ui.Select):
        assert interaction.guild is not None and interaction.message is not None \
            and interaction.message.embeds[0].description is not None \
            and isinstance(interaction.user, discord.Member)
        description = interaction.message.embeds[0].description

        # 付与するロールのリストを作る。
        roles, error = set(), None
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
            )), self.cog.role, error
        ))

    @discord.ui.button(label="ロールを消す", custom_id)


class RolePanel(Cog):
    def __init__(self, bot: RT):
        self.bot = bot

    @commands.Cog.listener()
    async def on_setup(self):
        self.bot.add_view(RolePanelView(self, timeout=None))

    @commands.command(
        aliases=("rp", "役職パネル", "ロールパネル", "やぱ", "ろぱ"), fsparent=FSPARENT,
        description="Create a role panel."
    )
    @discord.app_commands.describe(
        min_=(_d_mi := "The minimum number of roles that can be added."),
        max_=(_d_ma := "The maximum number of roles that can be added."),
        title=(_d_t := "Title of role panel."),
        content="Enter the name or ID of the role to be included in the role panel, separated by `<nl>`.",
    )
    async def role(
        self, ctx: commands.Context, min_: int = -1,  max_: int = -1,
        title: str = "Role Panel", *, content: str
    ):
        assert isinstance(ctx.channel, discord.TextChannel | discord.Thread) \
            and isinstance(ctx.author, discord.Member)
        emojis, content = extract_emojis(content), replace_nl(content)

        # Viewの設定を行う。
        view = RolePanelView(self, timeout=0)
        view.add_roles.min_values, view.add_roles.max_values = adjust_min_max(
            len(emojis), min_, max_
        )
        # ロールをオプションとして全て追加する。
        for emoji, role in (roles := [
            (emoji, await commands.RoleConverter().convert(ctx, id_))
            for emoji, id_ in emojis.items()
        ]):
            view.add_roles.add_option(label=role.name, value=str(role.id), emoji=emoji)
        view.add_roles.placeholder = t(dict(ja="ロールを設定する", en="Set roles"), ctx)

        await artificially_send(ctx.channel, ctx.author, embed=discord.Embed(
            title=title, description="\n".join(
                f"{emoji} {role.mention}" for emoji, role in roles
            ), color=ctx.author.color
        ), view=view)
        if ctx.interaction is not None:
            await ctx.interaction.response.send_message("Ok", ephemeral=True)


async def setup(bot: RT) -> None:
    await bot.add_cog(RolePanel(bot))