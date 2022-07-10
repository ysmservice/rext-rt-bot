# RT - Two-dimensional pocket

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .bot import RT
    from .general import t


bot: Optional[RT] = None