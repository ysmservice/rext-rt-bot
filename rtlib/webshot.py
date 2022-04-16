# RT - WebShot

from aiofiles import open as aioopen
from aiohttp import ClientSession


async def shot(url: str, path: str) -> None:
    "Webページの写真を撮ります。"
    async with ClientSession() as session:
        async with session.post("https://apiwebshot.dmsblog.cf/api", json={"url": url}) as r:
            async with aioopen(path, "wb") as f:
                await f.write(await r.read())


if __name__ == "__main__":
    from asyncio import run
    run(shot("https://www.google.co.jp", "test.png"))