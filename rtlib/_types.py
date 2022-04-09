# RT - Types

from typing import Union, TypeAlias

from discord.ext import commands


CmdGrp: TypeAlias = Union[commands.Command, commands.Group]
Text: TypeAlias = dict[str, str]