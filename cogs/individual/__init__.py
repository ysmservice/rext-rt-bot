# RT - Individual

from typing import cast, TypedDict, Literal
from collections.abc import AsyncIterator

from random import randint

from discord.ext import commands
import discord

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from jishaku.functools import executor_function
from aiofiles.os import remove
from PIL import Image

from core import RT, Cog, t

from rtutil.calculator import aiocalculate, NotSupported
from rtutil.collectors import make_google_url
from rtutil.minecraft import search, NotFound
from rtutil.views import EmbedPage
from rtutil.securl import check, get_capture
from rtlib.common import dumps

from data import Colors


FSPARENT = "individual"


class JinData(TypedDict):
    "オレ的ゲーム速報＠刃のデータの型です。"

    title: str
    url: str
    image: str


class Individual(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
        self.session = ClientSession(json_serialize=dumps)

    async def cog_unload(self):
        await self.session.close()

    @commands.command(description="Search minecraft user", fsparent=FSPARENT)
    @discord.app_commands.describe(user="Minecraft user name")
    async def minecraft(self, ctx, *, user: str):
        await ctx.typing()
        try:
            result = await search(self.session, user)
        except NotFound:
            await ctx.send(t(dict(
                ja="そのユーザーは見つかりません",
                en="I can't found that user"
            ), ctx))
        else:
            embed = Cog.Embed(title="Minecraft User")
            embed.add_field(name=t(dict(ja="名前", en="name"), ctx), value=result.name)
            embed.add_field(name="UUID", value=f"`{result.id}`")
            embed.set_image(url=result.skin)
            await ctx.send(embed=embed)
            
    (Cog.HelpCommand(minecraft)
        .set_description(ja="マイクラユーザー検索", en="minecraft user search")
        .add_arg(
            "user", "str", None,
            ja="マイクラのユーザ名",
            en="Minecraft user name"
        )
        .merge_headline(ja="マイクラのユーザー検索をします"))

    async def jin(self) -> AsyncIterator[JinData]:
        "オレ的ゲーム速報＠刃のスクレイピングをします。"
        async with self.bot.session.get("http://jin115.com") as r:
            soup = BeautifulSoup(await r.text(), "lxml")
        for article_soup in soup.find_all("div", class_="index_article_body"):
            thumbnail_anchor = article_soup.find("a")
            yield JinData(
                title=thumbnail_anchor.get("title"),
                url=thumbnail_anchor.get("href"),
                image=thumbnail_anchor.find("img").get("src")
            )

    @commands.command(
        "jin", aliases=("オレ的ゲーム速報＠刃", "オレ速"), fsparent=FSPARENT,
        description="オレ的ゲーム速報＠刃の最新のニュースを表示します。"
    )
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def jin_(self, ctx: commands.Context):
        await ctx.typing()
        embeds = []
        async for data in self.jin():
            embed = Cog.Embed(
                title=data["title"],
                url=data["url"],
                color=0x1e92d9
            )
            embed.set_image(url=data["image"])
            embed.set_footer(
                text="オレ的ゲーム速報＠刃",
                icon_url="https://cdn.discordapp.com/attachments/706794659183329291/781532922507034664/a3ztm-t6lmd.png"
            )
            embeds.append(embed)
        await EmbedPage(embeds).first_reply(ctx)

    (Cog.HelpCommand(jin_)
        .merge_headline(ja=jin_.description)
        .set_description(
            ja="[オレ的ゲーム速報＠刃](http://jin115.com)の最新のニュースを表示します。",
            en="View the latest news from [My Style Game News @ Blade](http://jin115.com). (language is japanese)"
        ))

    GAME_PACKAGE_SIZES = {
        "switch": ((370, 600), "L"),
        "ps4": ((653, 838), "1")
    }
    GAME_BASE_PATH = "data/images/game_maker/"
    GAME_SUPPORT_EXTS = ("png", "jpg", "PNG", "JPG", "GIF", "gif")
    GAME_SUPPORT_MODES = ("switch", "ps4")

    @executor_function
    def make_game_package(self, path: str, output_path: str, mode: str) -> None:
        "ゲームパッケージを作ります。"
        base_image = Image.open(f"{self.GAME_BASE_PATH}{mode}_base.png")
        base_image.paste(
            Image.open(path).resize(self.GAME_PACKAGE_SIZES[mode][0]),
            Image.open(f"{self.GAME_BASE_PATH}{mode}_mask.png")
                .convert(self.GAME_PACKAGE_SIZES[mode][1]) # type: ignore
        )
        base_image.save(output_path)

    @commands.command(
        "game", aliases=("g", "ゲーム"), fsparent=FSPARENT,
        description="Create a collage image of the game package."
    )
    @commands.cooldown(1, 10, commands.BucketType.user)
    @discord.app_commands.describe(mode="Type of game package.")
    async def game(self, ctx: commands.Context, mode: Literal["switch", "ps4"]):
        if mode not in self.GAME_SUPPORT_MODES:
            return await ctx.reply(t(
                {"ja": "そのゲームは対応していません。",
                 "en": "That game is not supported."},
            ctx))
        if not ctx.message.attachments:
            return await ctx.reply(t(
                {"ja": "画像を添付してください。",
                 "en": "You should send picture with command message."},
            ctx))
        attachment = ctx.message.attachments[0]
        if not attachment.filename.endswith(self.GAME_SUPPORT_EXTS):
            return await ctx.reply(t(
                {"ja": "そのファイルタイプは対応していません。",
                 "en": "Sorry, I don't know that file type."},
            ctx))
        await ctx.typing()
        input_path = "{}input_{}.{}".format(
            self.GAME_BASE_PATH, ctx.author.id,
            attachment.filename[attachment.filename.rfind('.')+1:]
        )
        await attachment.save(input_path) # type: ignore
        await self.make_game_package(
            input_path,
            (output_path := f"{self.GAME_BASE_PATH}output_{ctx.author.id}.png"),
            mode
        )
        await ctx.reply(file=discord.File(output_path))
        for path in (input_path, output_path):
            await remove(path)

    (Cog.HelpCommand(game)
        .merge_headline(ja="ゲームソフトのコラ画像を作ります。")
        .set_description(
            ja="ゲームソフトのコラ画像を作ります。\n渡された画像をゲームソフトのケースっぽくします。\n画像を添付してください。",
            en="Make a collage image of a game software.\nMake the image passed to you look like a game software case.\nPlease attach picture."
        )
        .add_arg("mode", "Choice",
            ja="どのゲーム機にするかです。\n`switch`: スイッチ\n`ps4`: Play Station 4",
            en="Which game console do you want to use? \n`switch`: switch\n`ps4`: Play Station 4"))

    FORTUNES = {
        "ja": {
            "超吉": (100, 101),
            "大大大吉": (98, 100),
            "大大吉": (96, 98),
            "大吉": (75, 96),
            "中吉": (65, 75),
            "小吉": (40, 65),
            "吉": (20, 40),
            "末吉": (10, 20),
            "凶": (4, 10),
            "大凶": (0, 4)
        },
        "en": {
            "Great nice good luck": (100, 101),
            "Great nice big luck": (98, 100),
            "Great big luck": (96, 98),
            "Big nice": (75, 96),
            "Medium nice": (65, 75),
            "Nice": (40, 65),
            "Good": (20, 40),
            "Ok": (10, 20),
            "Bad": (4, 10),
            "So bad": (0, 4)
        }
    }

    @commands.command(
        aliases=("おみくじ", "omikuji", "cookie", "luck", "oj"),
        description="Do omikuji (fortune telling).", fsparent=FSPARENT
    )
    async def fortune(self, ctx):
        i = randint(0, 100)
        for key, value in self.FORTUNES[self.bot.get_language("user", ctx.author.id)].items():
            if value[0] <= i < value[1]:
                await ctx.reply(
                    embed=Cog.Embed(
                        title=t(dict(ja="おみくじ", en="Omikuji (fortune telling)"), ctx),
                        description=t(dict(
                            ja="あなたの運勢は`{key}`です。", en="Your fortune today: `{key}`"
                        ), ctx, key=key)
                    ).set_footer(
                        text=t(dict(
                            ja="何回でもできますが、もちろんわかってますよね？",
                            en="You can do it as many times as you want, but of course you know what I mean."
                        ), ctx)
                    )
                )
                break

    (Cog.HelpCommand(fortune)
        .merge_headline(ja="おみくじを引きます。")
        .set_description(
            ja="おみくじを引きます。", en="Do omikuji (fortune telling)."
        ))

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
        
    @commands.command(
        aliases=("si", "サーバー情報"),
        description="Show server information", fsparent=FSPARENT
    )
    @discord.app_commands.describe(target="server id")
    async def serverinfo(self, ctx, target: int | None = None):
        guild = await self.bot.search_guild(target)
        embed = Cog.Embed(title=t({"ja": "{name}の情報","en": "{name}'s information"}, ctx, name=guild.name))
        embed.add_field(
            name=t({"ja": "サーバー名", "en": "Server name"}, ctx),
            value=f"{guild.name} (`{guild.id}`)"
        )
        embed.add_field(
            name=t({"ja": "サーバー作成日時", "en": "Server created at"}, ctx),
            value=f"<t:{int(guild.created_at.timestamp())}>"
        )
        embed.add_field(
            name=t({"ja": "サーバーの作成者", "en": "Server owner"}, ctx),
            value=f"{guild.owner} (`{guild.owner.id}`)"
        )
        embed.add_field(
            name=t({"ja": "サーバーのメンバー数", "en": "Server member count"}, ctx),
            value=f"{guild.member_count} ({guild.member_count - guild.members.count(lambda m: m.bot)})"
        )
        embed.add_field(
            name=t({"ja": "サーバーのチャンネル数", "en": "Server channel count"}, ctx),
            value=f"{len(guild.channels)} ({len(guild.text_channels)})"
        )
        await ctx.reply(embed=embed)
        
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
        
    (Cog.HelpCommand(userinfo)
        .merge_headline(ja="ユーザーを検索します。")
        .add_arg("user", "User", "Optional",
            ja="ユーザーのIDかメンションまたは名前です。", en="User's name, id or mention.")
        .set_description(ja="ユーザーを検索します", en="Search user"))

    (Cog.HelpCommand(serverinfo)
        .set_headline(ja="サーバーを検索します。")
        .add_arg("target", "int", "Optional",
            ja="サーバーのIDです。", en="Server's id.")
        .set_description(ja="サーバーを検索します", en="Search server"))

    (Cog.HelpCommand(calculate)
        .merge_headline(ja="計算機")
        .set_description(ja="計算機です。", en=calculate.description)
        .add_arg("expression", "str",
            ja="計算する式です。五十文字までです。\n`+-*/`に対応しています。",
            en="Expression to calculate. Up to 50 characters.\n`+-*/` is supported."))


async def setup(bot):
    await bot.add_cog(Individual(bot))
