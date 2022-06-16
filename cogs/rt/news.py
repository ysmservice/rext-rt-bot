# RT - news

from datetime import datetime

from discord.ext import commands

from core import Cog, DatabaseManager, cursor, RT


class DataManager(DatabaseManager):
    "ニュースを管理するぞ"
    
    def __init__(self, bot: RT):
        self.bot = bot

    async def prepare_table(self):
        await cursor.execute(
            """CREATE TABLE News(
                Id BIGINT, Title TEXT, Content TEXT, DateTime DATETIME
            );"""
        )
    
    async def add(self, id: int, title: str, content: str):
        await cursor.execute(
            "INSERT INTO News VALUES(%s, %s, %s, %s);",
            (id, title, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
        )


class News(Cog):
    "RT関連のニュース"

    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(bot)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.group(description="RT news.")
    async def news(self, ctx):
        await self.group_index(ctx)

    @news.command(description="Add news.")
    @commands.is_owner()
    @discord.app_commands.describe(title="title name", content="content")
    async def add(self, ctx, title: str, *, content: str):
        async with ctx.typing():
            await self.data.prepare_table(ctx.message.id, title, content)
            await ctx.send("追加しました")

    @news.command(description="Show news")
    @discord.app_commands.describe(news_id="News id")
    async def show(self, ctx, news_id: int | None = None):
        pass
    

async def setup(bot: RT) -> None:
    await bot.add_cog(News(bot))
