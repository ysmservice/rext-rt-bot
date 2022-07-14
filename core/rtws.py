# RT - WebSocket

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bot import RT


disconnected = False
def setup(bot: RT):
    async def exists(_, *args, **kwargs):
        await bot.exists(*args, **kwargs)

    bot.rtws.set_route(exists)

    # バックエンドのイベントを呼び出す。
    @bot.rtws.listen()
    async def on_ready():
        bot.dispatch("backend_connect")
        bot.dispatch("setup")
        global disconnected
        if disconnected:
            bot.dispatch("backend_reconnect")
            disconnected = False

    @bot.rtws.listen()
    async def on_close():
        global disconnected
        disconnected = True
        bot.dispatch("backend_disconnect")