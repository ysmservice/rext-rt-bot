# RT - Individual

from typing import cast

from discord.ext import commands
import discord

from aiohttp import ClientSession

from core import RT, Cog, t

from rtutil.calculator import aiocalculate, NotSupported
from rtutil.collectors import make_google_url
from rtutil.securl import check, get_capture

from rtlib.common import dumps

from data import Colors


FSPARENT = "individual"


class Individual(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.session = ClientSession(json_serialize=dumps)

    @commands.command(
        aliases=("suc", "セキュアール", "urlチェック", "check"), fsparent=FSPARENT,
        description="Use SecURL to access the URL destination."
    )
    @discord.app_commands.describe(url=(_d_u := "The url to be accessed."))
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def securl(self, ctx: commands.Context, *, url: str):
        await ctx.typing()
        try:
            data = await check(self.session, url)
        except ValueError:
            await ctx.reply(t(dict(
                ja="そのページへのアクセスに失敗しました。",
                en="Failed to access the URL."
            ), ctx))
        else:
            if data.get("status") == 0:
                warnings = {
                    key: data[key]
                    for key in ("viruses", "annoyUrl", "blackList")
                }
                embed = discord.Embed(
                    title="SecURL",
                    description=t(dict(
                        ja="このサイトは危険なウェブページである可能性があります！",
                        en="This site may be a dangerous web page!"
                    ), ctx)
                    if (warn := any(warnings.values()))
                    else t(dict(
                        ja="危険性はありませんでした。", en="There was no danger."
                    ), ctx), color=getattr(Colors, "error" if warn else "normal")
                )
                for contents, bool_ in zip(((
                    dict(ja="ウイルス", en="Is contained virus"),
                    dict(ja="未検出", en="No"),
                    dict(ja="**検出**", en="**Yes**")
                ),
                (
                    dict(ja="迷惑サイト", en="Is spammy web site"),
                    dict(ja="いいえ", en="No"), dict(ja="**はい**", en="**Yes**")
                ),
                (
                    dict(ja="ブラックリスト", en="Is registered as black"),
                    dict(ja="登録されていません。", en="No"),
                    dict(ja="**登録されています。**", en="**Yes**")
                )), warnings.values()):
                    embed.add_field(
                        name=t(contents[0], ctx), value=t(contents[int(bool(bool_)) + 1], ctx)
                    )
                embed.set_image(url=get_capture(data))
                embed.set_footer(
                    text="Powered by SecURL",
                    icon_url="https://www.google.com/s2/favicons?domain=securl.nu"
                )
                await ctx.reply(embed=embed, view=discord.ui.View(timeout=1).add_item(
                    discord.ui.Button(label=t(dict(
                        ja="スクリーンショット全体を見る", en="See full screenshot",
                    ), ctx), url=get_capture(data, True))
                ))
            else:
                await ctx.reply(data.get("message"))

    (Cog.HelpCommand(securl)
        .merge_headline(ja="SecURLを使ってURL先にアクセスします。")
        .set_description(ja="SecURLを使ってURL先にアクセスします。", en=securl.description)
        .add_arg("url", "str", ja="アクセスするURLです。", en=_d_u))
    del _d_u

    @commands.command(
        aliases=("google", "グーグル", "ggrks", "gg"), fsparent=FSPARENT,
        description="Create a search URL in Google."
    )
    @discord.app_commands.describe(query="Query for searching.")
    async def search(self, ctx: commands.Context, *, query: str):
        await ctx.reply(
            f"URL: {make_google_url(query)}",
            allowed_mentions=discord.AllowedMentions.none()
        )

    (Cog.HelpCommand(search)
        .merge_headline(ja="Googleの検索URLを作ります。")
        .set_description(ja="Googleの検索URLを作ります。", en=search.description)
        .add_arg("query", "str",
            ja="検索ワードです。", en="The word that you want to search."))

    @commands.command(
        aliases=("ui", "ユーザー検索", "ゆーざーいんふぉ", "<-これかわいい！"),
        description="Search user", fsparent=FSPARENT
    )
    @discord.app_commands.describe(tentative="User's name, mention or id")
    @discord.app_commands.rename(tentative="user")
    async def userinfo(self, ctx, *, tentative: str | None = None):
        tentative = tentative or ctx.author
        if isinstance(tentative, str):
            try:
                tentative = await commands.MemberConverter() \
                    .convert(ctx, tentative) # type: ignore
            except commands.BadArgument:
                try:
                    tentative = await commands.UserConverter() \
                        .convert(ctx, tentative) # type: ignore
                except commands.BadArgument:
                    try:
                        tentative = await commands.ObjectConverter() \
                            .convert(ctx, tentative) # type: ignore
                    except commands.BadArgument:
                        ...
                    assert not isinstance(tentative, str), {
                        "ja": "ユーザーが見つかりませんでした。",
                        "en": "The user is not found."
                    }
            if isinstance(tentative, discord.User | discord.Member):
                tentative = await self.bot.search_user(tentative.id) # type: ignore
        user = cast(discord.User | discord.Member, tentative)

        hypesquad = ""
        if user.public_flags is not None:
            if user.public_flags.hypesquad_bravery:
                hypesquad = "<:HypeSquad_Bravery:876337861572579350>"
            elif user.public_flags.hypesquad_brilliance:
                hypesquad = "<:HypeSquad_Brilliance:876337861643882506>"
            elif user.public_flags.hypesquad_balance:
                hypesquad = "<:HypeSquad_Balance:876337714679676968>"

        embed = Cog.Embed(
            title="{}{}".format(user, " **`{}BOT`**".format(
                "✅" if user.public_flags.verified_bot else ""
            ) if user.bot else ""), description=hypesquad, color=user.color
        )
        embed.add_field(name="ID", value=f"`{user.id}`")
        embed.add_field(
            name=t({"ja": "Discord登録日時", "en": "Discord register time"}, ctx),
            value="..." if user.created_at is None
                else f"<t:{int(user.created_at.timestamp())}> (UST)"
        )
        embed.add_field(
            name=t({"ja": "アバターURL", "en": "Avatar url"}, ctx),
            value=getattr(user.avatar, "url", None) or t(dict(ja="なし", en="None"), ctx),
            inline=False
        )
        embed.set_thumbnail(url=getattr(user.avatar, "url", ""))
        embeds = [embed]

        # もし実行したサーバーにいる人なら、サーバーでの情報も付け加える。
        user = await self.bot.search_member(ctx.guild, user.id)
        if isinstance(user, discord.Member):
            embed = Cog.Embed(
                title=t({"en": "At this server information", "ja": "このサーバーの情報"}, ctx),
                description=", ".join(role.mention for role in user.roles)
            )
            embed.add_field(
                name=t({"en": "Show name", "ja": "表示名"}, ctx),
                value=user.display_name
            )
            embed.add_field(
                name=t({"en": "Joined at", "ja": "参加日時"}, ctx),
                value="..." if user.joined_at is None
                    else f"<t:{int(user.joined_at.timestamp())}> (UST)"
            )
            embeds.append(embed)

        await ctx.send(embeds=embeds)
        
    (Cog.HelpCommand(userinfo)
        .merge_headline(ja="ユーザーを検索します。")
        .add_arg("user", "User", "Optional",
            ja="ユーザーのIDかメンションまたは名前です。", en="User's name, id or mention.")
        .set_description(ja="ユーザーを検索します", en="Search user"))

    @commands.command(
        aliases=("calc", "計算機", "電卓"), fsparent=FSPARENT,
        description="The calculator"
    )
    async def calculate(self, ctx: commands.Context, *, expression: str):
        await ctx.typing()
        try:
            await ctx.reply(f"`{await aiocalculate(expression[:50])}`")
        except (SyntaxError, NotSupported):
            await ctx.reply(t(dict(
                ja="使用できない文字があるか形式がおかしいまたは長すぎるため、計算をすることができませんでした。",
                en="The calculation could not be performed because there are characters that cannot be used or the format is incorrect or too long."
            ), ctx))

    (Cog.HelpCommand(calculate)
        .merge_headline(ja="計算機")
        .set_description(ja="計算機です。", en=calculate.description)
        .add_arg("expression", "str",
            ja="計算する式です。五十文字までです。\n`+-*/`に対応しています。",
            en="Expression to calculate. Up to 50 characters.\n`+-*/` is supported."))


async def setup(bot):
    await bot.add_cog(Individual(bot))