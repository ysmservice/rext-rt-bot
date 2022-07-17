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
    status=Status.dnd, activity=Game("booting")
)
bot.logger.info("Now loading...")


if __name__ == "__main__":
    try: bot.run(SECRET["token"], log_handler=None)
    except KeyboardInterrupt: ...
    bot.cachers.close()