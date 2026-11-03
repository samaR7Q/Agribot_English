"""Text-mode test of the real Live session: same model, prompt and tools as the browser, but the
farmer's turns are sent as text. Bashir still answers in audio; we read the output transcript.

    .venv/bin/python scripts/text_test.py                      # all conversations in tests/conversations.json
    .venv/bin/python scripts/text_test.py mandi_no_district    # one conversation
Writes test_results/<timestamp>.json and prints tool calls + answers per turn.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402

from _agent import config  # noqa: E402
from _agent.live_config import live_connect_config  # noqa: E402
from _agent.logic import new_state, run_tool  # noqa: E402
from _agent.prompt import GREETING_TRIGGER  # noqa: E402


async def run_turn(session, text: str, state: dict) -> dict:
    await session.send_realtime_input(text=text)
    said, tools, usage = [], [], []
    t0 = time.time()
    first_audio = None
    # receive() stops at each turn_complete. A turn that only made tool calls ends silently and
    # the spoken answer follows in a new turn, so keep reading until something was said.
    for _ in range(6):
        called = False
        async for msg in session.receive():
            if msg.tool_call:
                called = True
                responses = []
                for fc in msg.tool_call.function_calls:
                    result, state_new = run_tool(fc.name, fc.args or {}, state)
                    state.clear()
                    state.update(state_new)
                    tools.append({"name": fc.name, "args": fc.args, "status": result.get("status")})
                    responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response=result))
                await session.send_tool_response(function_responses=responses)
            sc = msg.server_content
            if sc:
                if sc.model_turn and first_audio is None:
                    first_audio = time.time() - t0
                if sc.output_transcription and sc.output_transcription.text:
                    said.append(sc.output_transcription.text)
            if msg.usage_metadata:
                usage.append(msg.usage_metadata.model_dump(exclude_none=True))
        if said or not called:
            break
    return {"farmer": text, "tools": tools, "bashir": "".join(said).strip(),
            "first_audio_s": round(first_audio or 0, 2), "usage": usage}


async def run_conversation(client, name: str, turns: list[str]) -> dict:
    state = new_state()
    out = {"name": name, "turns": []}
    async with client.aio.live.connect(model=config.LIVE_MODEL, config=live_connect_config()) as session:
        for text in [GREETING_TRIGGER, *turns]:
            result = await run_turn(session, text, state)
            result["state"] = {k: v for k, v in state.items() if v}
            out["turns"].append(result)
            tools = ", ".join(f"{t['name']}→{t['status']}" for t in result["tools"]) or "-"
            print(f"  F: {text}\n     tools: {tools}\n  B: {result['bashir']}\n")
    return out


async def main() -> None:
    if not config.GEMINI_API_KEY:
        sys.exit("GEMINI_API_KEY missing in .env")
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    convs = json.loads((ROOT / "tests" / "conversations.json").read_text())
    wanted = sys.argv[1:]
    results = []
    for name, turns in convs.items():
        if wanted and name not in wanted:
            continue
        print(f"=== {name}")
        try:
            results.append(await run_conversation(client, name, turns))
        except Exception as exc:
            print(f"  ERROR {exc}")
            results.append({"name": name, "error": str(exc)})
    out_dir = ROOT / "test_results"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(results, indent=1, default=str))
    print(f"saved {path}")


if __name__ == "__main__":
    asyncio.run(main())
