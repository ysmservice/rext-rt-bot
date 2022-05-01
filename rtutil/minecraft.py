from typing import Dict
from aiohttp import ClientSession


async def search(user: str) -> Data:
    async with ClientSession() as session:
        async with session.get(
            "https://api.mojang.com/users/profiles/minecraft/{}".format(user)
        ) as r:
            if r.status == 204:
                raise NotFound("I can't found that user")
            else:
                return Data(await r.json())
            
                
class NotFound(Exception):
    pass


class Data:
    def __init__(self, data: Dict[str, str]):
        self.data = data
        
    @property
    def name(self) -> str:
        return self.data["name"]
    
    @property
    def id(self) -> str:
        return self.data["id"]
    
    @property
    def skin(self) -> str:
        return "https://minecraft.tools/en/skins/getskin.php?name={}".format(
            self.name
        )
