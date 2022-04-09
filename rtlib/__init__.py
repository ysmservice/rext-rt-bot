# RT - Utils

from typing import Optional, Any

from discord.ext.commands import Cog as OriginalCog
from discord.ext.fslash import is_fslash
from discord import Embed as OriginalEmbed

from aiomysql import Pool, Cursor

from .bot import RT
from .cacher import Cacher, Cache, CacherPool
from .data_manager import DatabaseManager, cursor
from data.constants import Colors


__all__ = (
    "RT", "Cog", "Cacher", "Cache", "CacherPool",
    "DatabaseManager", "cursor", "Pool", "Cursor",
    "t", "cast"
)


class Embed(OriginalEmbed):
    def __init__(self, title: str, *args, **kwargs):
        kwargs["title"] = title
        if "color" not in kwargs:
            kwargs["color"] = Colors.normal
        super().__init__(*args, **kwargs)


class Cog(OriginalCog):
    "Extended cog"

    async def _inject(self, *args, **kwargs):
        await super()._inject(*args, **kwargs)
        self.__parent__ = __file__[:__file__.rfind("/")]
        self.__category__ = self.__parent__[__file__.rfind("/")+1:]

    def embed(self, **kwargs) -> Embed:
        "Make embed and set title to the cog name."
        return Embed(self.__cog_name__, **kwargs)


def _get_client(obj):
    return obj._state._get_client()


def t(text: dict[str, str], ctx: Any = None, **kwargs) -> str:
    """Extracts strings in the correct language from a dictionary of language code keys and their corresponding strings, based on information such as the `ctx` guild passed in.
    You can use keyword arguments to exchange strings like f-string."""
    # Extract client
    client: Optional[RT] = None
    if getattr(ctx, "message", None) and not is_fslash(ctx):
        client = _get_client(ctx.message)
    elif getattr(ctx, "guild", None):
        client = _get_client(ctx.guild)
    elif getattr(ctx, "channel", None):
        client = _get_client(ctx.channel)
    elif getattr(ctx, "user", None):
        client = _get_client(ctx.user)
    # Extract correct text
    if client is None:
        text = text.get("en", text["ja"]) # type: ignore
    else:
        language = None
        if getattr(ctx, "user", None):
            language = client.language.user.get(ctx.user.id)
        if language is None and hasattr(ctx, "author"):
            language = client.language.user.get(ctx.author.id)
        if language is None and hasattr(ctx, "guild"):
            language = client.language.guild.get(ctx.guild.id)
        if language is None: language = "en"
        text = text.get("en", text["ja"]) if language is None else text[language] # type: ignore
    return text.format(**kwargs) # type: ignore


def cast(**kwargs: dict[str, str]) -> str:
    return kwargs # type: ignore