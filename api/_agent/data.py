"""Static data: topics, districts, crop calendar, demo mandi rates, crop info cards."""
from __future__ import annotations

import difflib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _load(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def topics() -> dict:
    """key → topic dict (crops and livestock)."""
    return {t["key"]: t for t in _load("topics.json")["topics"]}


@lru_cache(maxsize=None)
def general_subjects() -> dict:
    return {g["key"]: g for g in _load("topics.json")["general"]}


@lru_cache(maxsize=None)
def districts() -> list:
    return _load("districts.json")


@lru_cache(maxsize=None)
def calendar() -> dict:
    return _load("crop_calendar.json")


@lru_cache(maxsize=None)
def mandi() -> dict:
    return _load("mandi_rates.json")


@lru_cache(maxsize=None)
def card(key: str) -> Optional[dict]:
    """Info card for a topic or general subject, or None if it hasn't been built yet."""
    path = DATA_DIR / "cards" / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _norm_place(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"\b(district|city|tehsil|mandi|zila|zilla)\b", " ", name)
    return re.sub(r"[^a-z ]", "", re.sub(r"\s+", " ", name)).strip()


@lru_cache(maxsize=None)
def _district_index() -> dict:
    index = {}
    for d in districts():
        for name in [d["district"], *d.get("aliases", [])]:
            index[_norm_place(name)] = d
            index[_norm_place(name).replace(" ", "")] = d
    return index


def find_district(name: Optional[str]) -> Optional[dict]:
    """Match a spoken district/city name to a known district (exact, alias, then close spelling)."""
    if not name:
        return None
    key = _norm_place(name)
    index = _district_index()
    if key in index:
        return index[key]
    if key.replace(" ", "") in index:
        return index[key.replace(" ", "")]
    close = difflib.get_close_matches(key, list(index), n=1, cutoff=0.82)
    return index[close[0]] if close else None
