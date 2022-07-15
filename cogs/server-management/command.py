# RT - Command

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from discord.ext import commands
import discord

from core import Cog, RT, t, DatabaseManager, cursor

from rtutil.content_data import ContentData, disable_content_json, to_text
from rtutil.views import separate_to_embeds, EmbedPage
from rtutil.utils import is_json

from rtlib.common.cacher import Cacher
from rtlib.common.json import dumps, loads

from data import (
    LIST_ALIASES, NO_MORE_SETTING, ALREADY_NO_SETTING,
    SET_ALIASES, DELETE_ALIASES, FORBIDDEN
)

from .__init__ import FSPARENT


@dataclass
class CommandData:
    "コマンドデータを格納するデータクラスです。"

    guild_id: int
    command: str
    response: ContentData
    full: bool

    @classmethod
    def from_row(cls, row: tuple) -> CommandData:
        "データベースの列のタプルからクラスのインスタンスを作ります。"
        return cls(*(row[:2] + (loads(row[2]), row[3])))


class DataManager(DatabaseManager):
    "セーブデータ管理用のクラスです。"

    def __init__(self, cog: OriginalCommand):
        self.cog = cog
        self.caches: defaultdict[int, dict[str, CommandData]] = defaultdict(dict)
        self.pool = self.cog.bot.pool

    async def prepare_table(self) -> None:
        "テーブルを作ります。"
        await cursor.execute(
            """CREATE TABLE IF NOT EXISTS OriginalCommand (
                GuildId BIGINT, Command TEXT, Response JSON, Full BOOLEAN
            );"""
        )
        async for row in self.fetchstep(cursor, "SELECT * FROM OriginalCommand;"):
            self.caches[row[0]][row[1]] = CommandData.from_row(row)

    async def read(self, guild_id: int, **_) -> list[CommandData]:
        "データを読み込みます。"
        await cursor.execute(
            "SELECT * FROM OriginalCommand WHERE GuildId = %s;",
            (guild_id,)
        )
        return list(map(CommandData.from_row, await cursor.fetchall()))

    async def exists(self, guild_id: int, command: str, **_) -> bool:
        "データの存在確認をします。"
        await cursor.execute(
            "SELECT Response FROM OriginalCommand WHERE GuildId = %s AND Command = %s LIMIT 1;",
            (guild_id, command)
        )
        return bool(await cursor.fetchone())

    MAX = 50

    async def write(self, guild_id: int, command: str, response: ContentData, full: bool) -> None:
        "データの書き込みをします。"
        if guild_id in self.caches and len(self.caches[guild_id]) >= self.MAX:
            raise Cog.reply_error.BadRequest(NO_MORE_SETTING)
        if await self.exists(guild_id, command, cursor=cursor):
            await cursor.execute(
                """UPDATE OriginalCommand SET Response = %s, Full = %s
                    WHERE GuildId = %s AND Command = %s;""",
                (dumps(response), full, guild_id, command)
            )
        else:
            await cursor.execute(
                "INSERT INTO OriginalCommand VALUES (%s, %s, %s, %s);",
                (guild_id, command, dumps(response), full)
            )
        self.caches[guild_id][command] = CommandData(guild_id, command, response, full)

    async def delete(self, guild_id: int, command: str) -> None:
        "データの削除をします。"
        if guild_id not in self.caches or command not in self.caches[guild_id]:
            raise Cog.reply_error.BadRequest(ALREADY_NO_SETTING)
        await cursor.execute(
            "DELETE FROM OriginalCommand WHERE GuildId = %s AND Command = %s;",
            (guild_id, command)
        )
        del self.caches[guild_id][command]

    async def clean(self) -> None:
        "データのお掃除をします。"
        await self.cog.bot.clean(cursor, "OriginalCommand", "GuildId")


class OriginalCommandReplyEventContext(Cog.EventContext):
    "コマンド返信時のイベントコンテキストです。"

    message: discord.Message
    data: CommandData


class OriginalCommand(Cog):
    "自動返信機能のコグです。"

    def __init__(self, bot: RT):
        self.bot = bot
        self.data = DataManager(self)
        self.sent: Cacher[discord.Member, int] = self.bot.cachers.acquire(15.0)

    async def cog_load(self):
        await self.data.prepare_table()

    @commands.Cog.listener()
    async def on_message_noprefix(self, message: discord.Message):
        if message.guild is not None and message.author.id != self.bot.application_id \
                and message.guild.id in self.data.caches \
                and isinstance(message.author, discord.Member) \
                and (now := self.sent.get(message.author, 0)) < 3:
            # 返信するべきか確認した後返信を行う。
            replied, detail, cmds = 0, "", []
            for command, data in self.data.caches[message.guild.id].items():
                if (data.full and command == message.content) \
                        or (not data.full and command in message.content):
                    replied += 1
                    try:
                        await message.reply(**disable_content_json(data.response.copy())["content"])
                    except discord.Forbidden:
                        detail = FORBIDDEN
                        break
                    else:
                        cmds.append(command)
                # 連続返信は三回まで行う。
                if replied == 3: break
            if replied:
                # 連投時に連続で返信しないようにする。
                self.sent[message.author] = now + 1
                self.bot.rtevent.dispatch("on_command_reply", OriginalCommandReplyEventContext(
                    self.bot, message.guild, "ERROR" if detail else "SUCCESS",
                    {"ja": "自動返信", "en": "Auto reply"}, detail or {
                        "ja": f"コマンド：{(cmds := ', '.join(cmds))}", "en": f"Commands: {cmds}"
                    }, self.command
                ))

    @commands.group(
        aliases=("cmd", "コマンド", "命令"), fsparent=FSPARENT,
        description="Auto reply feature"
    )
    async def command(self, ctx: commands.Context):
        await self.group_index(ctx)

    @command.command("set", aliases=SET_ALIASES, description="Set a command.")
    @discord.app_commands.describe(
        full=(_d_f := "Whether or not a full command name match is required as a condition for replying."),
        command=(_d_c := "The name of the command."), response="The response to be replied."
    )
    async def set_(self, ctx: commands.Context, full: bool, command: str, *, response: str):
        assert ctx.guild is not None
        async with ctx.typing():
            await self.data.write(
                ctx.guild.id, command, loads(response)
                    if is_json(response)
                    else ContentData(
                        content={"content": response},
                        author=ctx.author.id, json=True
                    ), full
            )
        await ctx.reply("Ok")

    @command.command(aliases=DELETE_ALIASES, description="Delete a command.")
    @discord.app_commands.describe(command=_d_c)
    async def delete(self, ctx: commands.Context, *, command: str) -> None:
        assert ctx.guild is not None
        async with ctx.typing():
            await self.data.delete(ctx.guild.id, command)
        await ctx.reply("Ok")

    del _d_c

    @command.command("list", aliases=LIST_ALIASES, description="Displays a list of commands.")
    async def list_(self, ctx: commands.Context):
        assert ctx.guild is not None
        await EmbedPage(list(separate_to_embeds("\n".join(
            "・{}：`{}` ({} {})".format(command, to_text(data.response), t(
                dict(ja='全一致：', en='FullMatch: '), ctx
            ), data.full)
            for command, data in self.data.caches[ctx.guild.id].items()
        ), lambda text: self.embed(description=text)))).first_reply(ctx)

    (Cog.HelpCommand(command)
        .merge_headline(ja="自動返信機能")
        .set_description(
            ja="""自動返信機能です。
                オリジナルのコマンドを作ることができます。
                また、「これでできないの」がメッセージに含まれた際に「そうだよ(便乗)」と返信するようにすることもできます。""",
            en="""Automatic reply function.
                You can create your original commands.
                You can also make them reply with "Yeah lol (taking a ship)" when "lol" is included in the message."""
        )
        .add_sub(Cog.HelpCommand(set_)
            .set_description(ja="コマンドを設定します。", en="Set the command.")
            .add_arg("full", "bool",
                ja="返信する条件としてメッセージとコマンドの文字が全て一致する必要があるかどうか。", en=_d_f)
            .add_arg("command", "str",
                ja="返信する条件としてメッセージと一緒または含まれてないといけない文字列です。",
                en="A string of characters that must be same with or in the message as a condition for replying.")
            .add_arg("response", "str",
                ja="返信内容です。`Get content`で取得したコードで指定することもできます。",
                en="Reply content. You can also specify it with the code retrieved with `Get content`.")
            .set_examples({
                "ja": "True a!tias Try it and see. (とりあえず自分で試して、結果を見ろ。)",
                "en": "True a!tias Try it and see."
            }, {
                "ja": "自分でやろうとしないですぐ人に聞く人に「とりあえず自分で試してみろ」ということをすぐ伝えるためのコマンドを作ります。",
                "en": 'Create a command to immediately tell people who are quick to ask others instead of trying to do it themselves, "Try it yourself anyway.'
            }))
        .add_sub(Cog.HelpCommand(delete)
            .set_description(ja="コマンドの設定を削除します。", en=delete.description)
            .add_arg("command", "str", ja="削除するコマンドです。", en="The command to be deleted."))
        .add_sub(Cog.HelpCommand(list_)
            .set_description(
                ja="登録されているコマンドのリストを表示します。",
                en="Displays a list of registered commands."
            )))
    del _d_f


async def setup(bot: RT) -> None:
    await bot.add_cog(OriginalCommand(bot))