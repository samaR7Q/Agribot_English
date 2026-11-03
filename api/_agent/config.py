"""Settings from .env (or the process environment)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
LIVE_MODEL = os.environ.get("LIVE_MODEL", "gemini-3.8-live")
VOICE = os.environ.get("LIVE_VOICE", "Charon")
# Optional shared passcode so a public demo URL can't burn the API key.
DEMO_PASSCODE = os.environ.get("DEMO_PASSCODE", "")
LOG_DIR = Path(os.environ.get("LOG_DIR", ROOT / "session_logs"))
MAX_CALL_MINUTES = int(os.environ.get("MAX_CALL_MINUTES", "15"))
