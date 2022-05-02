# rtutil - Minecraft User

from dataclasses import dataclass

from aiohttp import ClientSession


async def search(session: ClientSession, user: str) -> MinecraftUserData:
    async with session.get(
        "https://api.mojang.com/users/profiles/minecraft/{}".format(user)
    ) as r:
        if r.status == 204:
            raise NotFound("I can't found that user")
        else:
            data = await r.json()
            return MinecraftUserData(
                data["name"],
                data["id"],
                f"https://minecraft.tools/en/skins/getskin.php?name={user}"
            )
            
                
class NotFound(Exception):
    pass


@dataclass
class MinecraftUserData:
    name: str
    id: str
    skin: str
