"""The Live session config, shared by the browser token and the text-mode test runner."""
from __future__ import annotations

import datetime as dt

from . import config, data
from .prompt import system_instruction
from .tools import declarations


def live_connect_config() -> dict:
    return {
        "response_modalities": ["AUDIO"],
        "system_instruction": system_instruction(),
        "tools": [{"function_declarations": declarations()}],
        "speech_config": {"language_code": "en-US", "voice_config": {"prebuilt_voice_config": {"voice_name": config.VOICE}}},
        # Tap-to-talk: the browser sends activityStart / activityEnd, so background talk and
        # Bashir's own voice from the speaker don't start a turn.
        "realtime_input_config": {"automatic_activity_detection": {"disabled": True}},
        # Without a language the transcript sometimes came out in Spanish or Hindi script.
        "input_audio_transcription": {"language_codes": ["en-PK"], "custom_vocabulary": vocabulary()},
        "output_audio_transcription": {},
        # Drops old turns instead of ending the session at 15 minutes, and caps per-turn cost.
        "context_window_compression": {"sliding_window": {}},
    }


def vocabulary() -> list[str]:
    """Crop, animal and district names, plus the Urdu farming words farmers mix in."""
    words = {"mandi", "barani", "urea", "DAP", "whitefly", "Bashir"}
    for t in data.topics().values():
        words.add(t["name"].split(" (")[0])
        words.update(t["aliases"])
    for d in data.districts():
        words.add(d["district"])
    return sorted(words)


def create_ephemeral_token(client) -> str:
    """One-call token for the browser. Model, prompt and tools are locked in; the browser can
    only add session resumption."""
    now = dt.datetime.now(tz=dt.timezone.utc)
    token = client.auth_tokens.create(
        config={
            "uses": 1,
            "expire_time": now + dt.timedelta(minutes=config.MAX_CALL_MINUTES + 15),
            "new_session_expire_time": now + dt.timedelta(minutes=2),
            "live_connect_constraints": {"model": config.LIVE_MODEL, "config": live_connect_config()},
            "lock_additional_fields": [],
        }
    )
    return token.name
