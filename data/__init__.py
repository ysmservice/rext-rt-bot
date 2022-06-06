# RT - Data

from typing import TypedDict

from sys import argv

from orjson import loads


__all__ = (
    "SECRET", "DATA", "CANARY", "get_category", "HOST_PORT", "URL", "API_URL", "SHARD",
    "TEST", "PREFIXES", "ADMINS", "Colors", "EMOJIS", "SUPPORT_SERVER", "PERMISSION_TEXTS",
    "SETTING_NOTFOUND", "ALREADY_NO_SETTING", "TOO_LARGE_NUMBER", "TOO_SMALL_NUMBER",
    "TOO_SMALL_OR_LARGE_NUMBER", "NO_MORE_SETTING", "NUMBER_CANT_USED",
    "FORBIDDEN", "notfound", "NOTFOUND", "ROLE_NOTFOUND", "CHANNEL_NOTFOUND",
    "SET_ALIASES", "DELETE_ALIASES", "ADD_ALIASES", "REMOVE_ALIASES", "SHOW_ALIASES",
    "LIST_ALIASES", "OFF_ALIASES", "ON_ALIASES", "TOGGLE_ALIASES", "START_ALIASES",
    "STOP_ALIASES"
)


class Secret(TypedDict):
    token: str
    mysql: dict
with open("secret.json", "r") as f:
    SECRET: Secret = loads(f.read())


class BackendData(TypedDict):
    host: str
    port: int
class NormalData(TypedDict):
    backend: BackendData
with open("data.json", "r") as f:
    DATA: NormalData = loads(f.read())


HOST_PORT = "{}{}".format(
    DATA["backend"]["host"], "" if DATA["backend"]["port"] in (80, 443)
        else f":{DATA['backend']['port']}"
)
URL = "http{}://{}".format(
    "s" if DATA["backend"]["port"] == 443 else "",
    HOST_PORT
)
API_URL = URL.replace("://", "://api.", 1)


def get_category(category: str, language: str) -> str:
    "指定されたカテゴリーの名前を、指定された言語で取得します。"
    return CATEGORIES.get(category, {}).get(language, category)


TEST = argv[-1] != "production"
CANARY = "canary" in argv
SHARD = "shard" in argv
PREFIXES: tuple[str, ...]
if TEST:
    if CANARY:
        PREFIXES = ("r2!", "r2.", "r2,")
    else:
        PREFIXES = ("r3!", "r3.", "r3,")
else:
    PREFIXES = (
        "rt!", "Rt!", "rT!", "RT!", "rt.", "Rt.", "rT.", "RT.", "rt,", "Rt,", "rT,", "RT,",
        "りつ！", "りつ!", "りつ。", "りつ.", "りつ、", "りつ,"
    )
ADMINS = (
    634763612535390209, 667319675176091659, 266988527915368448,
    884692310166761504, 739702692393517076
)
"管理者のIDのリスト"


CATEGORIES = {
    "server-tool": {"ja": "サーバー ツール", "en": "Server Tool"},
    "server-management": {"ja": "サーバー 運営", "en": "Server Management"},
    "individual": {"ja": "個人", "en": "Individual"}, "rt": {"ja": "RT", "en": "RT"},
    "entertainment": {"ja": "娯楽", "en": "Entertainment"},
    "music": {"ja": "音楽", "en": "Music"}, "tts": {"ja": "読み上げ", "en": "TTS"}
}
"カテゴリーの別名が入った辞書"


class Colors:
    normal = 0x1e50a2
    success = 0x98d98e
    warning = 0xe6b422
    error = 0xb7282e
    unknown = 0xadadad


EMOJIS = {
    "error": "<:error:964733321546457128>",
    "success": "<:success:964733321462550538>",
    "unknown": "<:unknown:964725991471710268>",
    "warning": "<:warn:964733321441579008>",
    "lvup_local": "<:level_up_local:876339471832997888>",
    "lvup_global": "<:level_up_global:876339460252528710>",
    "check": "<:check_mark:885714065106808864>",
    "search": "<:search:876360747440017439>"
}


SUPPORT_SERVER = "https://discord.gg/ugMGw5w"


PERMISSION_TEXTS = {
    "administrator": {"ja": "管理者", "en": "Administrator"},
    "view_audit_log": {"ja": "監査ログを表示", "en": "View Audit Log"},
    "manage_guild": {"ja": "サーバーの管理", "en": "Manage Server"},
    "manage_roles": {"ja": "ロールの管理", "en": "Manage Roles"},
    "manage_channels": {"ja": "チャンネルの管理", "en": "Manage Channels"},
    "kick_members": {"ja": "メンバーをキック", "en": "Kick Members"},
    "ban_members": {"ja": "メンバーをBAN", "en": "Ban Members"},
    "create_instant_invite": {"ja": "招待を作成", "en": "Create Instant Invite"},
    "change_nickname": {"ja": "ニックネームの変更", "en": "Change Nickname"},
    "manage_nicknames": {"ja": "ニックネームの管理", "en": "Manage Nickname"},
    "manage_emojis": {"ja": "絵文字の管理", "en": "Manage Emojis"},
    "manage_webhooks": {"ja": "ウェブフックの管理", "en": "manage Webhooks"},
    "manage_events": {"ja": "イベントの管理", "en": "Manage Events"},
    "manage_threads": {"ja": "スレッドの管理", "en": "Manage Threads"},
    "use_slash_commands": {"ja": "スラッシュコマンドの使用", "en": "Use Slash Commands"},
    "view_guild_insights": {"ja": "テキストチャンネルの閲覧＆ボイスチャンネルの表示", "en": "View Guild Insights"},
    "send_messages": {"ja": "メッセージを送信", "en": "Send Messages"},
    "send_tts_messages": {"ja": "TTSメッセージを送信", "en": "Send TTS Messages"},
    "manage_messages": {"ja": "メッセージの管理", "en": "Manage Messages"},
    "embed_links": {"ja": "埋め込みリンク", "en": "Embed Links"},
    "attach_files": {"ja": "ファイルを添付", "en": "Attach Files"},
    "read_message_history": {"ja": "メッセージ履歴を読む", "en": "Read Message History"},
    "mention_everyone": {"ja": "@everyone、@here、全てのロールにメンション", "en": "Mention Everyone"},
    "external_emojis": {"ja": "外部の絵文字の使用", "en": "External Emojis"},
    "add_reactions": {"ja": "リアクションの追加", "en": "Add reactions"}
}
"権限の日本語での名前"


SETTING_NOTFOUND = {
    "ja": "設定が見つかりませんでした。",
    "en": "Setting not found."
}
ALREADY_NO_SETTING = {
    "ja": "既に設定がありません。", "en": "There are already no settings."
}
NO_MORE_SETTING = {
    "ja": "これ以上設定できません。", "en": "No further settings are possible."
}
TOO_LARGE_NUMBER = {
    "ja": "数が大きすぎます。", "en": "The number is too large."
}
TOO_SMALL_NUMBER = {
    "ja": "数が小さぎます。", "en": "The number is too small."
}
TOO_SMALL_OR_LARGE_NUMBER = {
    "ja": "数が小さいまたは大きぎます。", "en": "The number is too small or large."
}
NUMBER_CANT_USED = {
    "ja": "その数は使用できません。", "en": "That number cannot be used."
}
FORBIDDEN = dict(
    ja="権限がないため処理に失敗しました。",
    en="Processing failed due to lack of authorization."
)
notfound = lambda ja, en: dict(
    ja=f"{ja}が見つかりませんでした。", en=f"{en} was not found."
)
NOTFOUND = {"ja": "見つかりませんでした。", "en": "Not found."}
ROLE_NOTFOUND = notfound("ロール", "Role")
CHANNEL_NOTFOUND = notfound("チャンネル", "Channel")


SET_ALIASES = ("s", "設定")
DELETE_ALIASES = ("del", "削除")
ADD_ALIASES = ("a", "追加")
REMOVE_ALIASES = ("rm", "削除")
LIST_ALIASES = ("l", "リスト", "一覧")
SHOW_ALIASES = ("sw", "now", "見る", "現在")
OFF_ALIASES = ("オフ", "無効", "disable", "dis")
ON_ALIASES = ("オン", "有効", "enable", "ena")
TOGGLE_ALIASES = ("オンオフ", "onoff", "tgl", "switch")
START_ALIASES = ("st", "スタート", "開始", "すたと")
STOP_ALIASES = ("sp", "ストップ", "停止", "すとぷ")