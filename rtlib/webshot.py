from aiohttp import ClientSession
import asyncio
import io
import io

class WebShot:
    
    async def shot(self, url: str) -> io.BytesIO:
        """shot a webpage"""
        if not url.startswith(("https://", "http")):
            url = "https://" + url
        async with ClientSession() as session:
            async with session.post("https://apiwebshot.dmsblog.cf/api", json={"url": url}) as r:
                return io.BytesIO(await r.read())
        
if __name__ == "__main__":
    async def main():
        webshot = WebShot()
        with open("image.png", "wb") as f:
            f.write((await webshot.shot("https://example.com")).read())
            
    asyncio.run(main())
