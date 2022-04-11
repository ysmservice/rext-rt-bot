# RT by Rext

from asyncio import run

from rtlib.bot import RT
from data import SECRET


bot = RT()
bot.print("Now loading...")


try: run(bot.start(SECRET["token"]))
except KeyboardInterrupt: bot.print("Bye")