# RT - Utils

from typing import TypeAlias, Optional, Any

from discord.ext.commands import Cog as OriginalCog
from discord.ext.fslash import is_fslash
import discord

from aiomysql import Pool, Cursor

from .bot import RT
from .cacher import Cacher, Cache, CacherPool
from .data_manager import DatabaseManager, cursor
from .help import Help, HelpCommand, Text, gettext
from . import utils, views

from data.constants import Colors


__all__ = (
    "RT", "Cog", "Cacher", "Cache", "CacherPool",
    "DatabaseManager", "cursor", "Pool", "Cursor",
    "t", "cast", "Help"
)


class Embed(discord.Embed):
    def __init__(self, title: str, *args, **kwargs):
        kwargs["title"] = title
        if "color" not in kwargs:
            kwargs["color"] = Colors.normal
        super().__init__(*args, **kwargs)


def _get_client(obj):
    return obj._state._get_client()


def t(text: Text, ctx: Any = None, **kwargs) -> str:
    """Extracts strings in the correct language from a dictionary of language code keys and their corresponding strings, based on information such as the `ctx` guild passed in.
    You can use keyword arguments to exchange strings like f-string."""
    # Extract client
    client: Optional[RT] = None
    user = False
    if isinstance(ctx, (discord.User, discord.Member, discord.Object)):
        client = _get_client(ctx) # type: ignore
        user = True
    elif getattr(ctx, "message", None) and not is_fslash(ctx):
        client = _get_client(ctx.message)
    elif getattr(ctx, "guild", None):
        client = _get_client(ctx.guild)
    elif getattr(ctx, "channel", None):
        client = _get_client(ctx.channel)
    elif getattr(ctx, "user", None):
        client = _get_client(ctx.user)
    # Extract correct text
    if client is None:
        text = gettext(text, "en") # type: ignore
    else:
        language = None
        if user:
            language = client.language.user.get(ctx.id)
        else:
            if getattr(ctx, "user", None):
                language = client.language.user.get(ctx.user.id) # type: ignore
            if language is None and hasattr(ctx, "author"):
                language = client.language.user.get(ctx.author.id) # type: ignore
            if language is None and hasattr(ctx, "guild"):
                language = client.language.guild.get(ctx.guild.id) # type: ignore
            if language is None: language = "en"
        text = gettext(text, "en") if language is None else gettext(text, language) # type: ignore
    return text.format(**kwargs) # type: ignore


class Cog(OriginalCog):
    "Extended cog"

    Help, HelpCommand = Help, HelpCommand
    Embed = Embed
    t = staticmethod(t)
    UserMember: TypeAlias = discord.User | discord.Member

    def embed(self, **kwargs) -> Embed:
        "Make embed and set title to the cog name."
        return Embed(self.__cog_name__, **kwargs)


def cast(**kwargs: dict[str, str]) -> str:
    return kwargs # type: ignore