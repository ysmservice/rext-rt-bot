# RT Util- Panel

from typing import Any
from collections.abc import Sequence, Callable

import discord

from emoji import UNICODE_EMOJI_ENGLISH


__all__ = ("make_panel", "tally_panel", "extract_emojis")
EMOJIS = [chr(0x1f1e6 + i) for i in range(26)]


def make_panel(data: dict[str, str], space: str = " ") -> str:
    "パネルを作ります。"
    return "\n".join(f"{key}{space}{value}" for key, value in data.items())


def tally_panel(panel: str, spaces: Sequence[str] = (" ", "　")) -> dict[str, str]:
    "パネルから辞書でデータを取り出します。"
    return {
        line[:(i:=min(
            map(lambda s: line.find(s), spaces),
            key=lambda s: 2000 if s == -1 else s
        ))]: line[i+1:] for line in panel.splitlines()
    }


def extract_emojis(
    content: str, make_default: bool = True,
    on_end: Callable[[bool, dict[str, str]], Any] = lambda _, __: None
) -> dict[str, str]:
    "文字列の行にある絵文字とその横にある文字列を取り出す関数です。"
    i, emojis, result = -1, [], {}
    for line in content.splitlines():
        if line and line != "\n":
            i += 1
            not_mention: bool = "@" not in line

            if line[0] == "<" and all(char in line for char in (">", ":")):
                if not_mention or line.count(">") != 1:
                    # もし外部絵文字なら。
                    emojis.append(line[:line.find(">") + 1])
            elif line[0] in (UNICODE_EMOJI_ENGLISH or EMOJIS):
                # もし普通の絵文字なら。
                emojis.append(line[0])
            elif make_default:
                # もし絵文字がないのなら作る。
                emojis.append(EMOJIS[i])
                line = EMOJIS[i] + " " + line

            result[emojis[-1]] = line.replace(emojis[-1], "")

            # もし取り出した役職名の最初が空白なら空白を削除する。
            if result[emojis[-1]][0] in (" ", "　"):
                result[emojis[-1]] = result[emojis[-1]][1:]
            # もしメンションじゃないならメンションに変える。
            if not_mention:
                on_end(not_mention, result)

    return result