# RT by Rext

from asyncio import run

from utils.bot import RT
from data import SECRET


bot = RT()
bot.print("Now loading...")


@bot.listen()
async def on_ready():
    bot.print("Ready")


bot.print("Connecting...")


try: run(bot.start(SECRET["token"]))
except KeyboardInterrupt: bot.print("Bye")