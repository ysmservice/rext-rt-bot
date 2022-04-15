# RT Data - Constants

from re import A
from sys import argv


__all__ = ("TEST", "PREFIXES", "ADMINS", "Colors")


TEST = argv[-1] != "production"
if TEST:
    PREFIXES = ("r2!", "r2.", "r2,")
else:
    PREFIXES = (
        "rt!", "Rt!", "rT!", "RT!", "rt.", "Rt.", "rT.", "RT.", "rt,", "Rt,", "rT,", "RT,",
        "りつ！", "りつ!", "りつ。", "りつ.", "りつ、", "りつ,"
    )
"List of Rext developer id"
ADMINS = (
    634763612535390209, 667319675176091659, 266988527915368448,
    884692310166761504, 739702692393517076
)


"Category alias display in Help"
CATEGORIES = {
    "server-tool": {"ja": "サーバー ツール"}, "server-panel": {"ja": "サーバー パネル"},
    "server-safety": {"ja": "サーバー 安全"}, "individual": {"ja": "個人"},
    "entertainment": {"ja": "娯楽"}, "music": {"ja": "音楽", "en": "Music"},
    "tts": {"ja": "読み上げ", "en": "TTS"}
}


class Colors:
    normal = 0x1e50a2
    warning = 0xe6b422
    error = 0xb7282e
    unknown = 0xadadad