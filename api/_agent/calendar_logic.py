"""Sowing/harvest windows: parse the schedule strings and check a date or month against them."""
from __future__ import annotations

import calendar as _cal
import re
from datetime import date
from typing import List, Optional, Tuple

MONTHS = list(_cal.month_name)[1:]
_MONTH_NUM = {m.lower(): i for i, m in enumerate(MONTHS, 1)}
_MONTH_NUM.update({m[:3].lower(): i for i, m in enumerate(MONTHS, 1)})

# (month, day) → (month, day); may wrap over the new year (December to February).
Window = Tuple[Tuple[int, int], Tuple[int, int]]


def _point(text: str, is_end: bool) -> Optional[Tuple[int, int]]:
    text = text.strip().lower()
    m = re.search(r"(mid\s+)?(?:(\d{1,2})(?:st|nd|rd|th)?\s+)?([a-z]+)", text)
    if not m or m.group(3)[:3] not in _MONTH_NUM:
        return None
    month = _MONTH_NUM[m.group(3)[:3]]
    if m.group(1):
        day = 15
    elif m.group(2):
        day = int(m.group(2))
    else:
        day = _cal.monthrange(2025, month)[1] if is_end else 1
    return month, day


def parse_windows(value) -> List[Window]:
    """'1 July to 15 August' / ['..', '..'] → windows. Unparseable text ('100 to 120 Days') → []."""
    parts = value if isinstance(value, list) else [value]
    windows = []
    for part in parts:
        if not isinstance(part, str):
            continue
        part = re.sub(r"\(.*?\)", "", part)
        if " to " not in part:
            continue
        start, end = part.split(" to ", 1)
        a, b = _point(start, False), _point(end, True)
        if a and b:
            windows.append((a, b))
    return windows


def _in_window(md: Tuple[int, int], window: Window) -> bool:
    start, end = window
    if start <= end:
        return start <= md <= end
    return md >= start or md <= end


def date_in_windows(day: date, windows: List[Window]) -> bool:
    return any(_in_window((day.month, day.day), w) for w in windows)


def month_in_windows(month: int, windows: List[Window]) -> bool:
    last = _cal.monthrange(2025, month)[1]
    return any(
        any(_in_window((month, d), w) for d in range(1, last + 1))
        for w in windows
    )


def month_number(name: Optional[str]) -> Optional[int]:
    if not name:
        return None
    return _MONTH_NUM.get(name.strip().lower()[:3])
