# RT - WebShot

from asyncio import run

from aiofiles import open as aioopen
from aiohttp import ClientSession


async def shot(url: str, path: str) -> None:
    """Shot a webpage
    
    Parameters
    ----------
    url: strURL"""
    async with ClientSession() as session:
        async with session.post("https://apiwebshot.dmsblog.cf/api", json={"url": url}) as r:
            async with aioopen(path, "wb") as f:
                await f.write(await r.read())


if __name__ == "__main__":
    run(shot("https://www.google.co.jp", "test.png"))