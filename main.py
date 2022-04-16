# RT by Rext

from asyncio import run

from discord import Intents, Status, Game, AllowedMentions

from rtlib.bot import RT
from data import SECRET


intents = Intents.default()
intents.message_content = True
intents.members = True
bot = RT(
    allowed_mentions=AllowedMentions(everyone=False), intents=intents,
    status=Status.dnd, activity=Game("起動")
)
bot.print("Now loading...")


try: run(bot.start(SECRET["token"]))
except KeyboardInterrupt: bot.print("Bye")