"""Build English info cards (data/cards/<topic>.json) from the Urdu Agribot KB with a Gemini text model.

No RAG at run time: each card is a dict of aspect → a short English fact sheet, looked up by
get_topic_info. Run once (or again when the KB changes):

    .venv/bin/python scripts/build_cards.py                 # all topics
    .venv/bin/python scripts/build_cards.py wheat cow       # some topics
    .venv/bin/python scripts/build_cards.py --model gemini-x-flash --force
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from _agent import config  # noqa: E402

KB_DIR = Path.home() / "Documents/PB/Shahram_Workspace/Agribot/Agribot-RAG/data/specific_KB"
CARDS = ROOT / "data" / "cards"

CATEGORY_TO_ASPECT = {
    "OVERVIEW": "overview", "SEEDS AND VARIETIES": "varieties", "SEED RATE": "sowing",
    "SOWING METHODS": "sowing", "FERTILIZER APPLICATION": "fertilizer", "IRRIGATION": "irrigation",
    "PESTS & DISEASES": "pests_diseases", "WEEDS MANAGEMENT": "weeds",
    "HARVESTING AND POST-HARVESTING": "harvesting", "FARM MACHINIZATION": "machinery",
    "LAND HOLDING": "other", "FARMING TYPE": "other", "ANY OTHER": "other",
    "BREEDS": "breeds", "CARE & MANAGEMENT": "care", "SHED & DESIGN": "shed",
    "ANIMAL HEALTH & VACCINATION": "health", "MILKING": "milking", "FEED MANAGEMENT": "feed",
    "REPRODUCTION & BREEDING": "breeding", "DEWORMING": "deworming",
    "Climate Change Impact on Crops (Overview)": "overview",
    "Climate Change and Change in Sowing Time": "sowing_time_change",
    "Climate Change Impacts on Pests and Diseases": "pests_diseases",
    "Climate Change and Heat Waves": "heat_waves", "Climate Change and Frost": "frost",
    "IRRIGATION METHODS": "methods", "IRRIGATION BENEFITS": "benefits", "ECONOMICS": "economics",
}

CARD_PROMPT = """You are preparing reference notes for an English voice assistant that advises farmers in Pakistan.
Below are Urdu knowledge-base passages about {topic}, section "{aspect}".

Write an English fact sheet from them:
- Keep EVERY concrete fact: numbers, doses and units, dates and months, variety/breed names, product/chemical names, intervals, yields.
- Keep who each fact applies to: province or region (Punjab, Sindh, KP, Balochistan ...), irrigated vs rain-fed (barani), soil fertility, animal age/weight.
- Merge repeated facts. Drop greetings, filler and anything not about {topic}.
- Plain short sentences, grouped under short labels like "Irrigated Punjab:". No markdown symbols except the labels.
- Use only what the passages say. Do not add anything from your own knowledge.
- At most {max_words} words.

PASSAGES:
{passages}
"""

TIMING_PROMPT = """From these English notes about {topic}, give its sowing time and harvest time in Pakistan.
Answer only JSON: {{"sowing": "...", "harvesting": "..."}}. Use date ranges like "1 October to 15 November"
when the notes give them; otherwise a short phrase from the notes; use null if the notes don't say.

NOTES:
{notes}
"""


def pick_model(client, wanted: str | None) -> str:
    if wanted:
        return wanted
    names = []
    for m in client.models.list():
        name = m.name.split("/")[-1]
        actions = getattr(m, "supported_actions", None) or []
        if "flash" in name and "generateContent" in actions and not re.search(r"lite|live|tts|image|audio|thinking|exp", name):
            names.append(name)
    if not names:
        sys.exit("No flash text model found; pass --model")
    names.sort(key=lambda n: [int(x) if x.isdigit() else x for x in re.split(r"[.-]", n)], reverse=True)
    return names[0]


def generate(client, model: str, prompt: str, json_out: bool = False) -> str:
    from google.genai import types
    cfg = types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json" if json_out else None)
    for attempt in range(4):
        try:
            return client.models.generate_content(model=model, contents=prompt, config=cfg).text or ""
        except Exception as exc:  # rate limits, transient 5xx
            wait = 5 * (attempt + 1)
            print(f"    retry in {wait}s: {str(exc)[:120]}")
            time.sleep(wait)
    raise RuntimeError("generation failed")


def kb_rows(kb_folder: str) -> list:
    rows = []
    for path in sorted(glob.glob(str(KB_DIR / f"{kb_folder}_json" / "*.json"))):
        rows.extend(json.loads(Path(path).read_text(encoding="utf-8")))
    return rows


def build(client, model: str, key: str, name: str, kb_folder: str, is_crop: bool) -> dict:
    by_aspect: dict[str, list[str]] = {}
    for row in kb_rows(kb_folder):
        cats = (row.get("metadata") or {}).get("category") or ["ANY OTHER"]
        for aspect in {CATEGORY_TO_ASPECT.get(c, "other") for c in cats}:
            by_aspect.setdefault(aspect, []).append(row["text"].strip())
    card = {"topic": key, "name": name, "source": f"Agribot KB {kb_folder}", "model": model, "aspects": {}}
    for aspect, texts in sorted(by_aspect.items()):
        texts = list(dict.fromkeys(texts))
        # Big sections (sugarcane, cotton) go in batches and are merged in a last pass.
        batches, cur, size = [], [], 0
        for t in texts:
            if size + len(t) > 40000 and cur:
                batches.append(cur)
                cur, size = [], 0
            cur.append(t)
            size += len(t)
        batches.append(cur)
        parts = [generate(client, model, CARD_PROMPT.format(topic=name, aspect=aspect, max_words=450,
                                                            passages="\n\n".join(b))) for b in batches]
        sheet = parts[0] if len(parts) == 1 else generate(
            client, model, CARD_PROMPT.format(topic=name, aspect=aspect, max_words=600, passages="\n\n".join(parts)))
        card["aspects"][aspect] = sheet.strip()
        print(f"  {key}/{aspect}: {len(texts)} chunks → {len(sheet.split())} words")
    if is_crop:
        notes = "\n\n".join(card["aspects"].get(a, "") for a in ("sowing", "harvesting", "overview"))
        try:
            card["timing"] = json.loads(generate(client, model, TIMING_PROMPT.format(topic=name, notes=notes), json_out=True))
        except (ValueError, RuntimeError):
            card["timing"] = {}
    return card


def main() -> None:
    from google import genai
    parser = argparse.ArgumentParser()
    parser.add_argument("topics", nargs="*")
    parser.add_argument("--model")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not config.GEMINI_API_KEY:
        sys.exit("GEMINI_API_KEY missing in .env")
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    model = pick_model(client, args.model)
    print(f"model: {model}")

    topics = json.loads((ROOT / "data" / "topics.json").read_text())
    jobs = [(t["key"], t["name"], t["kb"], True if t["group"] == "crop" else False) for t in topics["topics"]]
    jobs += [(g["key"], g["name"], g["kb"], False) for g in topics["general"] if g["key"] != "about_bashir"]
    CARDS.mkdir(parents=True, exist_ok=True)
    for key, name, kb, is_crop in jobs:
        if args.topics and key not in args.topics:
            continue
        out = CARDS / f"{key}.json"
        if out.exists() and not args.force:
            print(f"skip {key} (exists)")
            continue
        print(f"{key} ← {kb}")
        card = build(client, model, key, name, kb, is_crop)
        out.write_text(json.dumps(card, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
