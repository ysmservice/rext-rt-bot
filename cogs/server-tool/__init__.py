# RT - Server Tool

from discord.ext import commands
import discord

from core import Cog, RT, t

from data import EMOJIS, PERMISSION_TEXTS, NOTFOUND


FSPARENT = "server-tool"


class ServerTool(Cog):
    def __init__(self, bot: RT):
        self.bot = bot

    @commands.command(
        aliases=("invs", "招待ランキング"), fsparent=FSPARENT,
        description="Invitation ranking is displayed."
    )
    async def invites(self, ctx: commands.Context):
        assert ctx.guild is not None
        await ctx.reply(embed=Cog.Embed(
            title=t(dict(
                ja="{guild_name}の招待ランキング",
                en="Invitation ranking of {guild_name}"
            ), ctx, guild_name=ctx.guild.name), description='\n'.join(
                f"{a}：`{c}`" for a, c in sorted((
                    (f"{i.inviter.mention}({i.code})", i.uses or 0)
                    for i in await ctx.guild.invites()
                    if i.inviter is not None and i.uses
                ), reverse=True, key=lambda x: x[1])
            )
        ))

    (Cog.HelpCommand(invites)
        .merge_headline(ja="招待ランキング")
        .set_description(ja="招待ランキングを表示します。", en=invites.description))

    @commands.command(
        aliases=("perms", "権限", "戦闘力"), fsparent=FSPARENT,
        description="Displays the permissions held by the specified member."
    )
    async def permissions(self, ctx: commands.Context, *, member: discord.Member | None = None):
        member = member or ctx.guild.default_role # type: ignore
        permissions = getattr(member, "guild_permissions", getattr(
            member, "permissions", None
        ))

        if permissions is None:
            await ctx.reply(t(dict(
                ja="見つかりませんでした。", en="Not found..."
            ), ctx))
        else:
            await ctx.reply(embed=Cog.Embed(
                title=t(
                    {"ja": "{name}の権限一覧", "en": "{name}'s Permissions"},
                    ctx, name=member.name # type: ignore
                ),
                description="\n".join(
                    f"{EMOJIS['success']} {t(PERMISSION_TEXTS[name], ctx)}"
                        if getattr(permissions, name, False)
                        else f"{EMOJIS['error']} {t(PERMISSION_TEXTS[name], ctx)}"
                    for name in PERMISSION_TEXTS
                )
            ))

    (Cog.HelpCommand(permissions)
        .merge_headline(ja="指定したユーザーが所有している権限を表示します。")
        .set_description(ja="指定したユーザーが所有している権限を表示します。", en=permissions.description)
        .add_arg("member", "Member", "Optional",
            ja="""所有している権限を見たい対象のメンバーです。
                指定しない場合は`@everyone`ロール(全員が持っている権限)となります。""",
            en="""The members of the target group who want to see the privileges they possess.
                If not specified, it will be the `@everyone` role (the authority that everyone has)."""))

    @commands.command(
        fsparent=FSPARENT, aliases=("si", "サーバー情報"),
        description="Show server information."
    )
    @discord.app_commands.describe(target="The id of server.")
    async def serverinfo(self, ctx, *, target: int | None = None):
        guild = ctx.guild if target is None else await self.bot.search_guild(target)
        if guild is None:
            raise Cog.BadRequest(NOTFOUND)
        embed = Cog.Embed(title=t({"ja": "{name}の情報","en": "{name}'s information"}, ctx, name=guild.name))
        embed.add_field(
            name=t({"ja": "サーバー名", "en": "Server name"}, ctx),
            value=f"{guild.name} (`{guild.id}`)"
        )
        embed.add_field(
            name=t({"ja": "サーバー作成日時", "en": "Server created at"}, ctx),
            value=f"<t:{int(guild.created_at.timestamp())}>"
        )
        if guild.owner is not None:
            embed.add_field(
                name=t({"ja": "サーバーの作成者", "en": "Server owner"}, ctx),
                value=f"{guild.owner} (`{guild.owner.id}`)"
            )
        if guild.member_count is not None:
            embed.add_field(
                name=t({"ja": "サーバーのメンバー数", "en": "Server member count"}, ctx),
                value="{} ({})".format(guild.member_count, guild.member_count - len(
                    set(filter(lambda m: m.bot, guild.members))
                ))
            )
        text, voice, count = 0, 0, 0
        for count, channel in enumerate(guild.channels, 1):
            if isinstance(channel, discord.TextChannel | discord.Thread):
                text += 1
            else:
                voice += 1
        embed.add_field(
            name=t({"ja": "サーバーのチャンネル数", "en": "Server channel count"}, ctx),
            value=t(dict(
                ja="`{sum_}` (テキストチャンネル：`{text_}`, ボイスチャンネル：`{voice}`)",
                en="`{sum_}` (Text channels: `{text_}`, Voice channels: `{voice}`)"
            ), ctx, sum_=count, text_=text, voice=voice)
        )
        await ctx.reply(embed=embed)

    (Cog.HelpCommand(serverinfo)
        .set_headline(ja="サーバーを検索します。")
        .add_arg("target", "int", "Optional",
            ja="サーバーのIDです。", en="Server's id.")
        .set_description(ja="サーバーを検索します", en="Search server"))


async def setup(bot: RT) -> None:
    await bot.add_cog(ServerTool(bot))