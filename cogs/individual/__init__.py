# RT - Individual

from typing import cast

from discord.ext import commands
import discord

from jishaku.functools import executor_function

from core import RT, Cog, t

from rtutil.calculator import aiocalculate, NotSupported
from rtutil.collectors import make_google_url


FSPARENT = "individual"


class Individual(Cog):
    def __init__(self, bot: RT):
        self.bot = bot

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