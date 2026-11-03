"""Tool handlers. Every rule that must not depend on the model lives here: topic switch,
missing-info probes, unsupported crops, mandi lookups, sowing windows.

The conversation state is a plain dict kept by the browser and sent with every tool call,
so the server stays stateless (Vercel functions).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from . import data
from .calendar_logic import MONTHS, date_in_windows, month_in_windows, month_number, parse_windows
from .tools import CROP_ASPECTS, GENERAL_ASPECTS, LIVESTOCK_ASPECTS

PK_TZ = ZoneInfo("Asia/Karachi")

EMPTY_STATE = {
    "topic": None,             # current crop/animal key
    "pending_switch": None,    # topic key waiting for the farmer's yes/no
    "district": None,
    "province": None,
    "farm_type": None,
    "soil_fertility": None,
    "harvest_resource": None,
    "animal_age": None,
    "animal_weight_kg": None,
    "probed": [],              # "topic:aspect" already probed once; never probe the same thing twice
}

PROBE_QUESTIONS = {
    "district": "Which district are you from?",
    "farm_type": "Is your land irrigated or rain-fed (barani)?",
    "soil_fertility": "Is your soil weak, medium, or very fertile?",
    "harvest_resource": "Will you harvest with labour or with a machine?",
    "animal_age": "How old is your animal?",
    "animal_weight_kg": "About how much does your animal weigh, in kilograms?",
}

# Profile fields an aspect needs before it can be answered well (same rules as the Urdu bot).
CROP_PROBES = {"varieties": ["district", "farm_type"], "fertilizer": ["soil_fertility"], "harvesting": ["harvest_resource"]}
FARM_TYPE_EXEMPT = {"rice", "sugarcane"}
LIVESTOCK_PROBES = {"health": ["animal_age", "animal_weight_kg"]}
ANIMAL_FIELDS = ("animal_age", "animal_weight_kg")

ANSWER_RULE = (
    "Answer the farmer's question using ONLY the facts in `info`, in 2 to 4 short spoken sentences. "
    "When `info` gives a dose or amount (spray, fertilizer, seed rate), say it with its unit. "
    "If there is more useful detail, offer it in one short line. If `info` does not cover the question, "
    "say you don't have that information. Never add doses, varieties, dates or prices that are not in `info`."
)


def today() -> datetime:
    return datetime.now(PK_TZ)


def new_state() -> dict:
    return {**EMPTY_STATE, "probed": []}


def _covered_list() -> str:
    crops = [t["name"] for t in data.topics().values() if t["group"] == "crop"]
    animals = [t["name"].lower() + "s" for t in data.topics().values() if t["group"] == "livestock"]
    return ", ".join(crops) + ", and " + " and ".join(animals)


def _topic_name(key: Optional[str]) -> str:
    return data.topics()[key]["name"] if key in data.topics() else (key or "")


# ── Topic ────────────────────────────────────────────────────────────────────

def select_topic(args: dict, state: dict) -> dict:
    topic = args.get("topic")
    said = (args.get("name_said") or "").strip()
    if topic not in data.topics():
        return {
            "status": "unsupported",
            "name": said or "that",
            "instruction": (
                f"Tell the farmer, kindly and in one or two sentences, that you can't help with {said or 'that'} yet. "
                f"Say you can help with these crops and animals: {_covered_list()}. Do not answer the question."
            ),
        }
    current = state.get("topic")
    if current is None or current == topic:
        state["topic"] = topic
        state["pending_switch"] = None
        return {"status": "ok", "topic": _topic_name(topic),
                "instruction": "Now call the tool that answers the question (get_topic_info or get_crop_timing)."}
    state["pending_switch"] = topic
    return {
        "status": "confirm_switch",
        "previous": _topic_name(current),
        "new": _topic_name(topic),
        "instruction": (
            f"Do not answer yet. Say exactly: 'Before I answer, please confirm: so far we were talking about "
            f"{_topic_name(current)}. Do you want to switch to {_topic_name(topic)}?' Then wait, and call "
            "confirm_switch with their answer."
        ),
    }


def confirm_switch(args: dict, state: dict) -> dict:
    pending = state.get("pending_switch")
    if not pending:
        return {"status": "nothing_pending", "instruction": "No switch was pending. Continue the conversation."}
    state["pending_switch"] = None
    if args.get("accepted"):
        state["topic"] = pending
        for field in ANIMAL_FIELDS:   # age/weight belonged to the previous animal
            state[field] = None
        return {"status": "switched", "topic": _topic_name(pending),
                "instruction": f"Now answer the farmer's earlier question about {_topic_name(pending)} (call the right tool)."}
    return {"status": "kept", "topic": _topic_name(state.get("topic")),
            "instruction": f"Stay on {_topic_name(state.get('topic'))}. Ask what they would like to know about it."}


# ── Crop / animal info ───────────────────────────────────────────────────────

def _missing_fields(topic: dict, aspect: str, state: dict) -> list:
    if topic["group"] == "livestock":
        needed = LIVESTOCK_PROBES.get(aspect, [])
    else:
        needed = list(CROP_PROBES.get(aspect, []))
        if topic["key"] in FARM_TYPE_EXEMPT and "farm_type" in needed:
            needed.remove("farm_type")
    return [f for f in needed if not state.get(f)]


def _probe(fields: list, state: dict, probe_key: str, retry_tool: str) -> dict:
    state.setdefault("probed", []).append(probe_key)
    questions = " ".join(PROBE_QUESTIONS[f] for f in fields)
    return {
        "status": "missing_info",
        "fields": fields,
        "instruction": (
            f"Before answering, ask the farmer this, in one short turn: \"{questions}\" "
            f"When they answer, call update_profile with what they said, then call {retry_tool} again."
        ),
    }


def get_topic_info(args: dict, state: dict) -> dict:
    key = state.get("topic")
    if not key:
        return {"status": "missing_info", "fields": ["topic"],
                "instruction": "Ask the farmer which crop or animal they are asking about, then call select_topic."}
    topic = data.topics()[key]
    aspect = args.get("aspect") or "overview"
    valid = LIVESTOCK_ASPECTS if topic["group"] == "livestock" else CROP_ASPECTS
    if aspect not in valid:
        aspect = "other"

    missing = _missing_fields(topic, aspect, state)
    probe_key = f"{key}:{aspect}"
    if missing and probe_key not in state.get("probed", []):
        return _probe(missing, state, probe_key, "get_topic_info")

    card = data.card(key)
    sections = (card or {}).get("aspects", {})
    info = sections.get(aspect) or ""
    if not info and aspect != "overview":
        info = sections.get("other") or ""
    if not info:
        return {"status": "no_info", "topic": topic["name"],
                "instruction": f"Say you don't have details on this for {topic['name']} yet. Don't guess."}
    context = {f: state.get(f) for f in ("province", "farm_type", "soil_fertility", "harvest_resource",
                                         "animal_age", "animal_weight_kg") if state.get(f)}
    rule = ANSWER_RULE
    if context:
        rule += " Fit the answer to the farmer's details in `farmer` (e.g. their province or land type) when `info` makes that distinction."
    return {"status": "ok", "topic": topic["name"], "aspect": aspect, "farmer": context, "info": info, "instruction": rule}


def get_general_info(args: dict, state: dict) -> dict:
    subject = args.get("subject")
    if subject not in GENERAL_ASPECTS:
        return {"status": "unsupported", "instruction": "Say you don't have information on that."}
    aspect = args.get("aspect") if args.get("aspect") in GENERAL_ASPECTS[subject] else GENERAL_ASPECTS[subject][0]
    sections = (data.card(subject) or {}).get("aspects", {})
    info = sections.get(aspect) or ""
    if not info:
        return {"status": "no_info", "instruction": "Say you don't have details on this yet. Don't guess."}
    return {"status": "ok", "subject": subject, "aspect": aspect, "info": info, "instruction": ANSWER_RULE}


# ── Profile ──────────────────────────────────────────────────────────────────

def update_profile(args: dict, state: dict) -> dict:
    saved, problems = {}, []
    if args.get("district"):
        match = data.find_district(args["district"])
        if match:
            state["district"], state["province"] = match["district"], match["province"]
            saved["district"] = f"{match['district']} ({match['province']})"
        else:
            problems.append(
                f"District '{args['district']}' was not found. Ask the farmer to say their district name again, "
                "or the nearest big city."
            )
    for field in ("farm_type", "soil_fertility", "harvest_resource", "animal_age"):
        if args.get(field):
            state[field] = str(args[field]).strip()
            saved[field] = state[field]
    weight = args.get("animal_weight_kg")
    if weight:
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            weight = 0
        if 20 <= weight <= 1500:
            state["animal_weight_kg"] = weight
            saved["animal_weight_kg"] = weight
        else:
            problems.append("That animal weight doesn't look right. Ask again in kilograms.")
    result = {"status": "ok" if not problems else "problem", "saved": saved}
    if problems:
        result["instruction"] = " ".join(problems)
    else:
        result["instruction"] = "Saved. Now call the tool you were going to call (it will use these details)."
    return result


# ── Mandi ────────────────────────────────────────────────────────────────────

def _spoken_rate(rate: dict) -> dict:
    return {"name": rate["name"], "unit": rate["unit"], "min": rate["min"], "max": rate["max"], "average": rate["avg"]}


def get_mandi_rate(args: dict, state: dict) -> dict:
    book = data.mandi()
    commodity = args.get("commodity") or "unknown"
    if commodity == "unknown":
        return {"status": "missing_info", "fields": ["commodity"],
                "instruction": "Ask: 'Which crop or animal's mandi rate would you like to know?' Then call get_mandi_rate again."}
    if commodity == "other" or (commodity not in book["commodities"] and commodity != "rice"):
        available = ", ".join(c["name"] for c in book["commodities"].values())
        name = args.get("other_name") or "that"
        return {"status": "unsupported",
                "instruction": f"Say you don't have the mandi rate for {name}. Rates available: {available}."}

    asked_place = args.get("district")
    if asked_place:
        place = data.find_district(asked_place)
        if not place:
            return {"status": "unknown_district",
                    "instruction": f"Say you couldn't find a mandi for '{asked_place}' and ask for the district name again."}
    elif state.get("district"):
        place = data.find_district(state["district"])
    else:
        return {"status": "missing_info", "fields": ["district"],
                "instruction": ("Ask: 'Which district are you in?' When they answer, call update_profile with that "
                                "district (it's their own), then call get_mandi_rate again.")}

    keys = ["rice_basmati", "rice_irri"] if commodity == "rice" else [commodity]
    market = book["mandis"][place["district"]]
    rates = [_spoken_rate(market["rates"][k]) for k in keys if k in market["rates"]]
    result = {"date": today().strftime("%d %B %Y"), "currency": "rupees"}
    if rates:
        return {**result, "status": "ok", "mandi": market["mandi"], "rates": rates,
                "instruction": ("Tell the farmer today's rate in this mandi: the average and the range (minimum to "
                                "maximum), with the unit (per 40 kg is one maund). Say numbers the way people say "
                                "them, e.g. 'three thousand six hundred rupees'. Keep it short.")}
    # Not traded there: point to the first mandi that has it, same province first.
    others = [d for d, m in book["mandis"].items() if any(k in m["rates"] for k in keys)]
    same_province = [d for d in others if book["mandis"][d]["province"] == place["province"]]
    nearest = (same_province or others or [None])[0]
    alt = book["mandis"][nearest] if nearest else None
    alt_rates = [_spoken_rate(alt["rates"][k]) for k in keys if k in alt["rates"]] if alt else []
    return {**result, "status": "not_traded_here", "asked_mandi": market["mandi"], "other_mandi": alt and alt["mandi"],
            "rates": alt_rates,
            "instruction": (f"Say {book['commodities'][keys[0]]['name']} is not traded in the {place['district']} mandi, "
                            f"and give the rate from {nearest} instead.")}


# ── Sowing calendar ──────────────────────────────────────────────────────────

def _calendar_display(name: str) -> str:
    for t in data.topics().values():
        if t.get("calendar") == name:
            return t["name"]
    return name


def _resolve_month(value: Optional[str]) -> int:
    now = today()
    if not value or value == "this month":
        return now.month
    if value == "next month":
        return now.month % 12 + 1
    return month_number(value) or now.month


def what_can_i_sow(args: dict, state: dict) -> dict:
    month = _resolve_month(args.get("month"))
    crops = [_calendar_display(c) for c in data.calendar()["sowing_calendar"].get(MONTHS[month - 1], [])]
    return {
        "status": "ok", "month": MONTHS[month - 1], "crops": crops,
        "instruction": ("Tell the farmer which of these crops they can sow in that month, as one short list. "
                        "Then offer to tell more about any one of them. Only these crops."),
    }


def get_crop_timing(args: dict, state: dict) -> dict:
    key = state.get("topic")
    if not key:
        return {"status": "missing_info", "fields": ["topic"],
                "instruction": "Ask which crop they mean, then call select_topic and get_crop_timing again."}
    topic = data.topics()[key]
    if topic["group"] == "livestock":
        return {"status": "not_applicable", "instruction": "Sowing and harvest times are for crops, not animals. Say so briefly."}

    kind = args.get("kind") or "both"
    schedule = data.calendar()["crop_schedule"].get(topic.get("calendar") or "", {})
    card_times = (data.card(key) or {}).get("timing", {})
    sowing = schedule.get("Preferred Sowing Time") or card_times.get("sowing")
    harvest = schedule.get("Harvesting Time") or card_times.get("harvesting")
    result = {"status": "ok", "crop": topic["name"]}
    if kind in ("sowing", "both"):
        result["sowing_time"] = sowing or "not known"
    if kind in ("harvesting", "both"):
        result["harvest_time"] = harvest or "not known"

    when = (args.get("when") or "").strip().lower()
    windows = parse_windows(sowing) if sowing else []
    if when and kind != "harvesting" and windows:
        now = today()
        if when in ("today", "now", "this week"):
            ok = date_in_windows(now.date(), windows)
            label, month = "today", now.month
        else:
            month = month_number(when) or now.month
            ok = month_in_windows(month, windows)
            label = MONTHS[month - 1]
        others = [_calendar_display(c) for c in data.calendar()["sowing_calendar"].get(MONTHS[month - 1], [])
                  if c != topic.get("calendar")]
        result["check"] = {"when": label, "can_sow": ok}
        result["other_crops_this_month"] = others
        result["instruction"] = (
            "Start with a clear yes or no. Give the sowing window. If no, also say which other crops can be sown "
            "then (other_crops_this_month). Keep it short."
        )
    else:
        result["instruction"] = "Give the time(s) in one or two short sentences. Only use these times."
    if (kind != "harvesting" and not sowing) or (kind != "sowing" and not harvest):
        result["instruction"] += " If a time is 'not known', say you don't have that information."
    return result


HANDLERS = {
    "select_topic": select_topic,
    "confirm_switch": confirm_switch,
    "get_topic_info": get_topic_info,
    "get_general_info": get_general_info,
    "update_profile": update_profile,
    "get_mandi_rate": get_mandi_rate,
    "what_can_i_sow": what_can_i_sow,
    "get_crop_timing": get_crop_timing,
}


def run_tool(name: str, args: Optional[dict], state: Optional[dict]) -> Tuple[dict, dict]:
    """Run one tool call. Returns (result for the model, updated state)."""
    state = {**new_state(), **(state or {})}
    handler = HANDLERS.get(name)
    if not handler:
        return {"status": "error", "instruction": f"Unknown tool {name}."}, state
    try:
        return handler(dict(args or {}), state), state
    except Exception as exc:  # never let a tool error kill the call
        return {"status": "error", "error": str(exc)[:200],
                "instruction": "Something went wrong looking that up. Apologise briefly and ask them to try again."}, state
