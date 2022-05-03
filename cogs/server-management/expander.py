# RT - Expander

from discord.ext import commands

from core import RT, Cog, t


PATTERN =  (
    "https://(ptb.|canary.)?discord(app)?.com/channels/"
    "(?P<guild>[0-9]{18})/(?P<channel>[0-9]{18})/(?P<message>[0-9]{18})"
)


