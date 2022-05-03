# RT - General

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, Optional, Any

from discord.ext.commands import Cog as OriginalCog
from discord.ext.fslash import is_fslash
import discord

from rtlib.common.utils import make_error_message, code_block

from .utils import get_fsparent, gettext
from .types_ import NameIdObj, MentionIdObj
from .bot import RT

from data import Colors

if TYPE_CHECKING:
    from .rtevent import EventContext
    from .help import Help, HelpCommand, Text


__all__ = ("RT", "Cog", "t", "cast", "Embed")


class Embed(discord.Embed):
    "Botのテーマカラーをデフォルトで設定するようにした`Embed`です。"

    def __init__(self, title: str, *args, **kwargs):
        kwargs["title"] = title
        kwargs.setdefault("color", Colors.normal)
        super().__init__(*args, **kwargs)


def _get_client(obj):
    return obj._state._get_client()


def t(text: Text, ctx: Any, **kwargs) -> str:
    """Extracts strings in the correct language from a dictionary of language code keys and their corresponding strings, based on information such as the `ctx` guild passed in.
    You can use keyword arguments to exchange strings like f-string."""
    # Extract client
    client: Optional[RT] = None
    user, gu = False, False
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
    elif gu := isinstance(ctx, (discord.Guild, discord.User)):
        client = _get_client(ctx) # type: ignore
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
            if language is None and getattr(ctx, "author", None):
                language = client.language.user.get(ctx.author.id) # type: ignore
            if language is None and getattr(ctx, "guild", None):
                language = client.language.guild.get(ctx.guild.id) # type: ignore
            if language is None and gu:
                language = client.language.guild.get(ctx.id)
            if language is None: language = "en"
        text = gettext(text, "en") if language is None else gettext(text, language) # type: ignore
    return text.format(**kwargs) # type: ignore


UCReT = TypeVar("UCReT")
class Cog(OriginalCog):
    "Extended cog"

    get_fsparent = staticmethod(get_fsparent)
    Help: type[Help]
    HelpCommand: type[HelpCommand]
    Embed = Embed
    ERRORS = {
        "WRONG_WAY": lambda ctx: t(dict(
            ja="使い方が違います。", en="This is wrong way to use this command."
        ), ctx)
    }
    t = staticmethod(t)
    FORBIDDEN = dict(
        ja="権限がないため処理に失敗しました。", en="Processing failed due to lack of authorization."
    )
    EventContext: type[EventContext]
    bot: RT

    @staticmethod
    def mention_and_id(obj: MentionIdObj) -> str:
        return f"{obj.mention} (`{obj.id}`)"

    @staticmethod
    def name_and_id(obj: NameIdObj) -> str:
        return f"{obj.name} (`{obj.id}`)"

    def embed(self, **kwargs) -> Embed:
        "Make embed and set title to the cog name."
        return Embed(self.__cog_name__, **kwargs)

    CONSTANT_FOR_EXCEPTION_TO_TEXT = {
        "ja": "内部エラーが発生しました。", "en": "An internal error has occurred."
    }

    @staticmethod
    def error_to_text(error: Exception) -> Text:
        error = code_block(make_error_message(error), "python") # type: ignore
        return {
            key: f"{Cog.CONSTANT_FOR_EXCEPTION_TO_TEXT[key]}\n{error}"
            for key in ("ja", "en")
        }


def cast(**kwargs: dict[str, str]) -> str:
    return kwargs # type: ignore