# RT - Recruitment Panel

from __future__ import annotations

from typing import Any, cast

from datetime import datetime
from time import time

from discord.ext import commands
import discord

from core import RT, Cog, t

from rtutil.converters import DateTimeConverter
from rtutil.utils import replace_nl

from .__init__ import FSPARENT


class RecruitmentPanelView(discord.ui.View):
    "募集パネルのViewです。"

    def __init__(self, *args, ctx: Any = None, **kwargs):
        super().__init__(*args, **kwargs)
        if ctx is not None:
            self.join_or_leave.label = t(dict(ja="参加または辞退", en="join / leave"), ctx)
            self.close_button.label = t(dict(ja="締め切る", en="Close"), ctx)

    @discord.ui.button(custom_id="recruitment.join_or_leave", emoji="📋")
    async def join_or_leave(self, interaction: discord.Interaction, _):
        assert interaction.message is not None
        embed = interaction.message.embeds[0].copy()
        if embed.description is None:
            embed.description = ""
        assert embed.fields[1].value is not None \
            and embed.fields[2].value is not None

        # 締め切り期限を切っている可動かをチェックする。
        if time() >= int(embed.fields[1].value[3:-1]):
            return await self.close(interaction)

        if interaction.user.mention in embed.description:
            embed.description = "\n".join(
                line for line in embed.description.splitlines()
                if line != interaction.user.mention
            )
        elif embed.description.count("@") < int(embed.fields[2].value):
            embed.description += f"\n{interaction.user.mention}"
        else:
            return await interaction.response.send_message(t(dict(
                ja="募集最大人数に達したため、あなたをこの募集に参加させることができません。",
                en="I am unable to accept you into this recruitment because I have reached our maximum number of applicants."
            ), interaction), ephemeral=True)

        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(
        custom_id="recruitment.close",
        style=discord.ButtonStyle.danger,
        emoji="💾"
    )
    async def close_button(self, interaction: discord.Interaction, _):
        "締め切りボタンです。"
        assert interaction.message is not None
        if interaction.message.content == str(interaction.user.id):
            # 即時締め切りを行う。
            await self.close(interaction)
        else:
            await interaction.response.send_message(t(dict(
                ja="あなたはこの募集パネルの作成者ではないため、即時締め切りをすることはできません。",
                en="You are not the creator of this recruitment panel and cannot close it."
            ), interaction), ephemeral=True)

    async def close(self, interaction: discord.Interaction) -> None:
        "募集パネルを締め切ります。"
        assert interaction.message is not None
        view: RecruitmentPanelView = discord.ui.View.from_message(interaction.message) # type: ignore
        view.children[0].disabled = True; view.children[1].disabled = True # type: ignore
        await interaction.response.edit_message(content="**{}**".format(t(dict(
            ja="この募集は締め切りました", en="This recruitment panel was closed"
        ), interaction)), view=view)


class RecruitmentPanel(Cog):
    "募集パネルを作るためのコマンドを実装したコグです。"

    def __init__(self, bot: RT):
        self.bot = bot

    @commands.Cog.listener()
    async def on_setup(self):
        self.bot.add_view(RecruitmentPanelView(timeout=None))

    @commands.command(
        description="Create a recruitment panel.", fsparent=FSPARENT,
        aliases=("recruit", "rec", "募集パネル", "募集", "ぼす")
    )
    @commands.cooldown(1, 10, commands.BucketType.user)
    @discord.app_commands.rename(max_="max", deadline_="deadline")
    async def recruitment(
        self, ctx: commands.Context, title: str, deadline_: DateTimeConverter,
        max_: int, *, detail: str
    ):
        deadline = cast(datetime, deadline_)
        detail = replace_nl(detail)
        await ctx.send(str(ctx.author.id), embed=Cog.Embed(title).add_field(
            name=t(dict(ja="詳細", en="Detail"), ctx),
            value=detail, inline=False
        ).add_field(
            name=t(dict(ja="締め切り", en="Deadline"), ctx),
            value=f"<t:{int(deadline.timestamp())}>"
        ).add_field(
            name=t(dict(ja="最大募集人数", en="Max"), ctx), value=str(max_)
        ), view=RecruitmentPanelView(ctx=ctx, timeout=0.0))

    (Cog.HelpCommand(recruitment)
        .merge_description(en="Create a recruitment panel.", ja="募集パネルを作ります。")
        .add_arg("title", "str", ja="募集パネルのタイトルです。", en="Title of the recruitment panel.")
        .add_arg("deadline", "DateTimeConverter",
            ja="日時です。`10-22,00:00`のように指定できます。(10月22日の0時0分)",
            en="Date and time. It can be specified as `10-22,00:00`(00:00 on October 22)."
        )
        .add_arg("max", "int", ja="最大募集人数です。", en="Maximum number of applicants.")
        .add_arg("detail", "str", ja="募集パネルの内容です。", en="Details of the recruitment panel."))


async def setup(bot: RT) -> None:
    await bot.add_cog(RecruitmentPanel(bot))