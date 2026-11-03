"""Session logs: one JSON event per line, per session, in session_logs/<date>/<session_id>.jsonl."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from . import config

_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]")


def write(session_id: str, event: dict) -> None:
    session_id = _SAFE_ID.sub("", session_id or "unknown")[:80] or "unknown"
    now = datetime.now(timezone.utc)
    event = {"ts": now.isoformat(timespec="milliseconds"), **event}
    folder = config.LOG_DIR / now.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / f"{session_id}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
