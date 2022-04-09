# RT Data - Constants

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
"Rext developers"
ADMINS = (
    634763612535390209, 667319675176091659, 266988527915368448,
    884692310166761504, 739702692393517076
)


class Colors:
    normal = 0x1e50a2
    warning = 0xe6b422
    error = 0xb7282e
    unknown = 0xadadad