# RT - Types

from typing import TypedDict, Union, TypeAlias, Any

from discord.ext import commands
import discord


__all__ = (
    "CmdGrp", "Text", "UserMember", "Channel", "StrKeyDict", "CommandInfo"
)


StrKeyDict: TypeAlias = dict[str, Any]


CmdGrp: TypeAlias = Union[commands.Command, commands.Group]
Text: TypeAlias = dict[str, str]
UserMember: TypeAlias = discord.User | discord.Member
Channel: TypeAlias = discord.abc.GuildChannel | discord.Thread | discord.abc.PrivateChannel


class CommandInfo(TypedDict):
    name: str
    category: str