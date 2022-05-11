# RT - WebSocket

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .bot import RT


disconnected = False
def setup(bot: RT):
    bot.ipcs.set_route(bot.exists)

    # バックエンドのイベントを呼び出す。
    @bot.ipcs.listen()
    async def on_connect():
        bot.dispatch("backend_connect")
        bot.dispatch("setup")
        global disconnected
        if disconnected:
            bot.dispatch("backend_reconnect")
            disconnected = False

    @bot.ipcs.listen()
    async def on_disconnect():
        global disconnected
        disconnected = True
        bot.dispatch("backend_disconnect")