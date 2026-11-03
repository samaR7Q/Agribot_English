# Kisan Dost Bashir: English demo (Gemini Live)

This is a voice-only English farming advisor.
- The browser talks to **Gemini Live** directly, using a one-call token from our server.
- Every farming rule runs in our own Python tools: topic switch, missing-info questions, unsupported crops, mandi lookups and sowing windows.
- It is hosted on this machine, behind a cloudflared HTTPS link (the mic needs HTTPS).

```
public/            front end (plain HTML/CSS/JS, no build step)
api/index.py       FastAPI: /api/session (token), /api/tool (tool calls), /api/log, and the page itself
api/_agent/        prompt, tool declarations, tool logic, data loading, logs
data/              topics, districts (120), crop calendar, demo mandi rates, cards/ (English crop info, 26 files)
scripts/           gen_mandi.py, build_cards.py, text_test.py (live text-mode tests), ws_smoke.py (browser-path check)
tests/             unit tests for the tool logic + conversations.json for text_test.py
run.sh / stop.sh   start / stop the app (127.0.0.1:5040) and the tunnel, by saved PIDs
session_logs/      one JSONL file per call: transcripts, tool calls, token usage
```

## Run
```bash
./run.sh               # app + cloudflared tunnel; prints the public https URL
./run.sh --no-tunnel   # app only, http://localhost:5040
./stop.sh
```
- `.env` holds the settings: `GEMINI_API_KEY`, `LIVE_MODEL`, `LIVE_VOICE`, `DEMO_PASSCODE`, `MAX_CALL_MINUTES`.
- **The tunnel URL changes every time it restarts.**
- Use headphones on a laptop so Bashir doesn't hear himself.
- **Tap-to-talk.** The first tap connects and Bashir greets. After that, each tap starts or stops recording, and audio is sent only while the mic is red. After 2 idle minutes the connection closes, and the next tap resumes it.
- Tester script: `docs/TEST_CONVERSATIONS.md`.

## Tests
```bash
.venv/bin/python -m pytest -q tests          # tool logic, no API calls
.venv/bin/python scripts/text_test.py        # real Live session, text in, transcript out (all conversations)
.venv/bin/python scripts/ws_smoke.py         # exact browser path: token → WebSocket → greeting → tool call
```

## Notes
- **Mandi rates are made up** (`scripts/gen_mandi.py`, seeded). They are not real prices.
- **Crop cards** are English summaries of the Agribot Urdu KB.
  - 13 were written by Gemini (`scripts/build_cards.py`): wheat, maize, rice, sugarcane, canola, sesame, mustard, raya, toria, taramira, camelina, linseed, guar.
  - 13 were written by hand: cotton, sunflower, berseem, lucerne, oats, ryegrass, mooli, hay, apple, cow, buffalo, climate change, irrigation.
- **The demo has no login** unless `DEMO_PASSCODE` is set. In that case testers enter the passcode once.
