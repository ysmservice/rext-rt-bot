# RT Util - Minecraft User

from dataclasses import dataclass

from aiohttp import ClientSession


__all__ = ("NotFound", "MinecraftUserData", "search")


class NotFound(Exception):
    "Minecraftのユーザー検索に失敗した際に発生します。"


@dataclass
class MinecraftUserData:
    "Minecraftのユーザーのデータを格納するためのデータクラスです。"

    name: str
    id: str
    skin: str


async def search(session: ClientSession, user: str) -> MinecraftUserData:
    "Minecraftのユーザーを検索します。"
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