# RT by Rext

from asyncio import run

from discord import Intents, Status, Game, AllowedMentions

from core.bot import RT
from data import SECRET, SHARD, NormalData

try: from uvloop import install
except ModuleNotFoundError: ...
else: install()

    
kwargs = {}
if SHARD:
    if NormalData["shard"] != "auto":
        kwargs["shard_ids"] = NormalData["shard"]

intents = Intents.default()
intents.message_content = True
intents.members = True
bot = RT(
    allowed_mentions=AllowedMentions(everyone=False), intents=intents,
    status=Status.dnd, activity=Game("起動"), **kwargs
)
bot.print("Now loading...")


try: run(bot.start(SECRET["token"]))
except KeyboardInterrupt: bot.print("Bye")
