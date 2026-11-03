"""Smoke test of the exact browser path: token from /api/session, raw WebSocket to the
constrained endpoint, greeting, one text question with tool calls via /api/tool.

    .venv/bin/python scripts/ws_smoke.py [base_url] ["question"]
"""
import asyncio
import json
import sys
import urllib.request

import websockets

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5040"
QUESTION = sys.argv[2] if len(sys.argv) > 2 else "What is the wheat rate in Multan?"
WS = ("wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha."
      "GenerativeService.BidiGenerateContentConstrained")


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


async def turn(ws, text, session_id, state):
    await ws.send(json.dumps({"realtimeInput": {"text": text}}))
    said, audio_bytes, tool_turn = [], 0, False
    while True:
        try:
            msg = json.loads(await asyncio.wait_for(ws.recv(), 20))
        except asyncio.TimeoutError:
            return "".join(said).strip() + " [timeout]", audio_bytes
        if "--debug" in sys.argv:
            print("   msg", {k: (list(v) if isinstance(v, dict) else v) for k, v in msg.items() if k != "usageMetadata"})
        if "toolCall" in msg:
            tool_turn = True
            responses = []
            for fc in msg["toolCall"]["functionCalls"]:
                r = post("/api/tool", {"session_id": session_id, "name": fc["name"], "args": fc.get("args", {}), "state": state})
                state.clear()
                state.update(r["state"])
                print(f"   tool {fc['name']}({json.dumps(fc.get('args', {}))}) → {r['result'].get('status')}")
                responses.append({"id": fc["id"], "name": fc["name"], "response": r["result"]})
            await ws.send(json.dumps({"toolResponse": {"functionResponses": responses}}))
        sc = msg.get("serverContent", {})
        for part in sc.get("modelTurn", {}).get("parts", []):
            audio_bytes += len(part.get("inlineData", {}).get("data", "")) * 3 // 4
        if sc.get("outputTranscription", {}).get("text"):
            said.append(sc["outputTranscription"]["text"])
        if sc.get("turnComplete"):
            if tool_turn and not said:
                continue   # the turn that only made the tool call; the spoken answer comes in a new turn
            return "".join(said).strip(), audio_bytes


async def main():
    s = post("/api/session", {})
    state = s["state"]
    async with websockets.connect(f"{WS}?access_token={s['token']}", max_size=None) as ws:
        await ws.send(json.dumps({"setup": {"model": f"models/{s['model']}", "sessionResumption": {}}}))
        first = json.loads(await asyncio.wait_for(ws.recv(), 20))
        print("setup:", list(first))
        for text in (s["greeting_trigger"], QUESTION):
            said, audio = await turn(ws, text, s["session_id"], state)
            print(f"F: {text}\nB: {said}\n   audio {audio / 48000:.1f}s\n")


asyncio.run(main())
