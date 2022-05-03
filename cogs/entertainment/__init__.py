# RT - Entertainment

from typing import TypedDict, Literal
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

from rtutil.minecraft import search, NotFound
from rtutil.views import EmbedPage


class JinData(TypedDict):
    "オレ的ゲーム速報＠刃のデータの型です。"

    title: str
    url: str
    image: str


class Entertainment(Cog):
    def __init__(self, bot: RT):
        self.bot = bot
    
    async def cog_load(self):
        self.session = ClientSession()

    async def cog_unload(self):
        await self.session.close()

    FSPARENT = "entertainment"

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


async def setup(bot: RT):
    await bot.add_cog(Entertainment(bot))