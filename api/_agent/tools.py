"""Function declarations sent to Gemini Live. The handlers live in logic.py."""
from __future__ import annotations

from . import data
from .calendar_logic import MONTHS

CROP_ASPECTS = ["overview", "varieties", "sowing", "fertilizer", "irrigation", "pests_diseases",
                "weeds", "harvesting", "machinery", "other"]
LIVESTOCK_ASPECTS = ["overview", "breeds", "care", "shed", "health", "milking", "feed", "breeding",
                     "deworming", "other"]
GENERAL_ASPECTS = {
    "climate_change": ["overview", "sowing_time_change", "pests_diseases", "heat_waves", "frost"],
    "irrigation": ["methods", "benefits", "economics"],
}


def _enum(values):
    return {"type": "STRING", "enum": list(dict.fromkeys(values))}


def declarations() -> list:
    topic_keys = list(data.topics())
    mandi_keys = list(data.mandi()["commodities"])
    return [
        {
            "name": "select_topic",
            "description": (
                "Call this FIRST whenever the farmer asks about a specific crop or animal, including its "
                "sowing or harvest time, before any other crop/animal tool. Use the crop or animal the farmer "
                "actually said in this turn (or the current topic if they didn't name one). If they name a "
                "crop, vegetable, fruit or animal that isn't in the list, use topic='other'. If they say "
                "'not X, Y', use Y. Do NOT call it for mandi rates or 'what can I sow' questions."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "topic": _enum(topic_keys + ["other"]),
                    "name_said": {"type": "STRING", "description": "The crop/animal name exactly as the farmer said it."},
                },
                "required": ["topic", "name_said"],
            },
        },
        {
            "name": "confirm_switch",
            "description": "Call with the farmer's answer after you asked whether they want to switch to the new crop/animal.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"accepted": {"type": "BOOLEAN", "description": "true if the farmer said yes."}},
                "required": ["accepted"],
            },
        },
        {
            "name": "get_topic_info",
            "description": (
                "Get the facts to answer a question about the current crop or animal. Call select_topic first. "
                "Pick the aspect that matches the question."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "aspect": _enum(CROP_ASPECTS + LIVESTOCK_ASPECTS),
                    "question": {"type": "STRING", "description": "The farmer's question, in short English."},
                },
                "required": ["aspect", "question"],
            },
        },
        {
            "name": "update_profile",
            "description": (
                "Save details the farmer gave about THEMSELVES: their own district, their land, their animal. "
                "Only pass the fields they actually said. animal_age is the animal's age only, never how long it "
                "has been sick or pregnant, and never the farmer's own age. Don't save a city the farmer only "
                "asked mandi rates for."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "district": {"type": "STRING", "description": "The farmer's own district or city."},
                    "farm_type": _enum(["irrigated", "rain-fed"]),
                    "soil_fertility": _enum(["weak", "medium", "fertile"]),
                    "harvest_resource": _enum(["labour", "machine"]),
                    "animal_age": {"type": "STRING", "description": "e.g. '3 years', '8 months'."},
                    "animal_weight_kg": {"type": "NUMBER"},
                },
            },
        },
        {
            "name": "get_mandi_rate",
            "description": (
                "Mandi (market) rate of a crop or animal. Does not change the conversation topic. If the farmer "
                "named a city for the rate, pass it as district; otherwise leave district empty and the saved "
                "district is used. Use commodity='other' for anything not in the list."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "commodity": _enum(mandi_keys + ["rice", "unknown", "other"]),
                    "other_name": {"type": "STRING", "description": "Name said, when commodity is 'other'."},
                    "district": {"type": "STRING", "description": "City/district named for this rate, if any."},
                },
                "required": ["commodity"],
            },
        },
        {
            "name": "what_can_i_sow",
            "description": "Which crops can be sown in a month (default: this month). Does not change the topic.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"month": _enum(["this month", "next month", *MONTHS])},
            },
        },
        {
            "name": "get_crop_timing",
            "description": (
                "Sowing and/or harvest time of the current crop, and whether it can be sown on a given day or "
                "month. Call select_topic first."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "kind": _enum(["sowing", "harvesting", "both"]),
                    "when": {"type": "STRING", "description": "'today', a month name, or empty."},
                },
                "required": ["kind"],
            },
        },
        {
            "name": "get_general_info",
            "description": "Facts on climate change and farming, or irrigation methods. Does not change the topic.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "subject": _enum(list(GENERAL_ASPECTS)),
                    "aspect": _enum([a for v in GENERAL_ASPECTS.values() for a in v]),
                },
                "required": ["subject", "aspect"],
            },
        },
    ]
