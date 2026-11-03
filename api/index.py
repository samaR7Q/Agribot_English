"""FastAPI app: the API (/api/*) and the front end (public/). Run with `uvicorn api.index:app`."""
from __future__ import annotations

import secrets
import sys
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _agent import config, logstore  # noqa: E402
from _agent.live_config import create_ephemeral_token  # noqa: E402
from _agent.logic import new_state, run_tool  # noqa: E402
from _agent.prompt import GREETING_TRIGGER  # noqa: E402

app = FastAPI(title="Agribot English")
_genai_client = None


def _client():
    global _genai_client
    if _genai_client is None:
        from google import genai
        if not config.GEMINI_API_KEY:
            raise HTTPException(500, "GEMINI_API_KEY is not set")
        # Ephemeral tokens are v1alpha only (SDK note); the browser connects to v1alpha too.
        _genai_client = genai.Client(api_key=config.GEMINI_API_KEY, http_options={"api_version": "v1alpha"})
    return _genai_client


def _check_passcode(passcode: str | None) -> None:
    if config.DEMO_PASSCODE and not secrets.compare_digest(passcode or "", config.DEMO_PASSCODE):
        raise HTTPException(401, "passcode required")


class SessionRequest(BaseModel):
    session_id: str | None = None
    resume: bool = False


class ToolRequest(BaseModel):
    session_id: str
    call_id: str | None = None
    name: str
    args: dict | None = None
    state: dict | None = None


class LogRequest(BaseModel):
    session_id: str
    events: list[dict]


@app.get("/api/health")
def health():
    return {"ok": True, "model": config.LIVE_MODEL}


@app.post("/api/session")
def start_session(req: SessionRequest, x_demo_passcode: str | None = Header(default=None)):
    _check_passcode(x_demo_passcode)
    session_id = req.session_id or secrets.token_hex(8)
    token = create_ephemeral_token(_client())
    logstore.write(session_id, {"event": "session_resumed" if req.resume else "session_started",
                                "model": config.LIVE_MODEL, "voice": config.VOICE})
    return {
        "token": token,
        "model": config.LIVE_MODEL,
        "session_id": session_id,
        "state": new_state(),
        "greeting_trigger": GREETING_TRIGGER,
        "max_call_minutes": config.MAX_CALL_MINUTES,
    }


@app.post("/api/tool")
def tool(req: ToolRequest, x_demo_passcode: str | None = Header(default=None)):
    _check_passcode(x_demo_passcode)
    result, state = run_tool(req.name, req.args, req.state)
    logstore.write(req.session_id, {"event": "tool", "name": req.name, "args": req.args, "result": result,
                                    "state": state})
    return {"result": result, "state": state}


@app.post("/api/log")
def log(req: LogRequest, x_demo_passcode: str | None = Header(default=None)):
    _check_passcode(x_demo_passcode)
    for event in req.events[:200]:
        logstore.write(req.session_id, event)
    return {"ok": True}


_PUBLIC = Path(__file__).resolve().parent.parent / "public"
if _PUBLIC.exists():
    @app.get("/")
    def index():
        return FileResponse(_PUBLIC / "index.html")

    app.mount("/", StaticFiles(directory=_PUBLIC), name="public")
