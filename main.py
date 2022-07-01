# RT by Rext

from asyncio import run

from discord import Intents, Status, Game, AllowedMentions

from core.bot import RT
from data import SECRET

try: from uvloop import install
except ModuleNotFoundError: ...
else: install()


intents = Intents.default()
intents.message_content = True
intents.members = True
bot = RT(
    allowed_mentions=AllowedMentions(everyone=False), intents=intents,
<<<<<<< HEAD
<<<<<<< HEAD
    status=Status.dnd, activity=Game("起動"),
=======
    status=Status.dnd, activity=Game("起動")
>>>>>>> 9a0de802606df2f292333f3b8f336925034206e7
=======
    status=Status.dnd, activity=Game("起動")
>>>>>>> 9a0de802606df2f292333f3b8f336925034206e7
)
bot.print("Now loading...")


try: run(bot.start(SECRET["token"]))
except KeyboardInterrupt: bot.print("Bye")