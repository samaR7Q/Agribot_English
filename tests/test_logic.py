import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

from _agent import data, logic  # noqa: E402
from _agent.calendar_logic import month_in_windows, parse_windows  # noqa: E402
from _agent.logic import run_tool  # noqa: E402
from _agent.tools import declarations  # noqa: E402


@pytest.fixture
def fixed_today(monkeypatch):
    def _set(y, m, d):
        monkeypatch.setattr(logic, "today", lambda: datetime(y, m, d, 10, 0, tzinfo=logic.PK_TZ))
    return _set


def test_first_topic_is_set_without_confirmation():
    result, state = run_tool("select_topic", {"topic": "wheat", "name_said": "gandum"}, None)
    assert result["status"] == "ok" and state["topic"] == "wheat"


def test_topic_switch_is_direct():
    _, state = run_tool("select_topic", {"topic": "wheat", "name_said": "wheat"}, None)
    result, state = run_tool("select_topic", {"topic": "maize", "name_said": "maize"}, state)
    assert result["status"] == "ok" and state["topic"] == "maize"


def test_animal_details_reset_on_new_animal():
    _, state = run_tool("select_topic", {"topic": "buffalo", "name_said": "buffalo"}, None)
    _, state = run_tool("update_profile", {"animal_age": "5 years", "animal_weight_kg": 500}, state)
    _, state = run_tool("select_topic", {"topic": "buffalo", "name_said": "bhains"}, state)
    assert state["animal_age"] == "5 years"
    _, state = run_tool("select_topic", {"topic": "cow", "name_said": "cow"}, state)
    assert state["topic"] == "cow" and state["animal_age"] is None and state["animal_weight_kg"] is None


def test_unsupported_crop_lists_covered_topics():
    result, state = run_tool("select_topic", {"topic": "other", "name_said": "tomato"}, None)
    assert result["status"] == "unsupported" and "tomato" in result["instruction"]
    assert "Wheat" in result["instruction"] and state["topic"] is None


def test_info_without_topic_does_not_ask_back():
    result, _ = run_tool("get_topic_info", {"aspect": "fertilizer", "question": "which fertilizer"}, None)
    assert result["status"] == "no_topic" and "Don't ask" in result["instruction"]


@pytest.mark.parametrize("topic,aspect", [("wheat", "varieties"), ("rice", "varieties"), ("wheat", "fertilizer"),
                                          ("wheat", "harvesting"), ("buffalo", "health")])
def test_answers_without_probing(topic, aspect):
    _, state = run_tool("select_topic", {"topic": topic, "name_said": topic}, None)
    result, _ = run_tool("get_topic_info", {"aspect": aspect, "question": aspect}, state)
    assert result["status"] == "ok" and result["info"]
    assert "Never ask the farmer" in result["instruction"]


def test_update_profile_district_alias_and_typo():
    result, state = run_tool("update_profile", {"district": "Lyallpur"}, None)
    assert state["district"] == "Faisalabad" and state["province"] == "Punjab"
    _, state = run_tool("update_profile", {"district": "Faislabad district"}, None)
    assert state["district"] == "Faisalabad"
    result, state = run_tool("update_profile", {"district": "Atlantis"}, None)
    assert result["status"] == "problem" and state["district"] is None


def test_animal_weight_out_of_range_rejected():
    result, state = run_tool("update_profile", {"animal_weight_kg": 5}, None)
    assert result["status"] == "problem" and state["animal_weight_kg"] is None


def test_mandi_without_district_gives_pakistan_rate_and_never_changes_topic():
    _, state = run_tool("select_topic", {"topic": "wheat", "name_said": "wheat"}, None)
    result, state = run_tool("get_mandi_rate", {"commodity": "maize"}, state)
    assert result["status"] == "ok_pakistan" and result["rates"][0]["name"] == "Maize"
    r = result["rates"][0]
    assert r["min"] <= r["average"] <= r["max"] and r["mandis"] > 1
    result, state = run_tool("get_mandi_rate", {"commodity": "maize", "district": "multan"}, state)
    assert result["status"] == "ok" and result["rates"][0]["name"] == "Maize"
    assert state["topic"] == "wheat" and state["district"] is None   # asked city is not saved


def test_mandi_rice_gives_both_types_and_unknown_commodity():
    result, _ = run_tool("get_mandi_rate", {"commodity": "rice", "district": "Lahore"}, None)
    assert [r["name"] for r in result["rates"]] == ["Basmati paddy", "IRRI-6 paddy"]
    result, _ = run_tool("get_mandi_rate", {"commodity": "unknown"}, None)
    assert result["status"] == "no_commodity" and "Wheat" in result["instruction"]
    result, _ = run_tool("get_mandi_rate", {"commodity": "wheat", "district": "Atlantis"}, None)
    assert result["status"] == "ok_pakistan" and "Atlantis" in result["instruction"]
    result, _ = run_tool("get_mandi_rate", {"commodity": "other", "other_name": "onion"}, None)
    assert result["status"] == "unsupported" and "onion" in result["instruction"]


def test_mandi_not_traded_points_elsewhere():
    result, _ = run_tool("get_mandi_rate", {"commodity": "cotton", "district": "Skardu"}, None)
    assert result["status"] == "not_traded_here" and result["rates"]


def test_what_can_i_sow_this_and_next_month(fixed_today):
    fixed_today(2026, 11, 2)
    result, _ = run_tool("what_can_i_sow", {}, None)
    assert result["month"] == "November" and "Wheat" in result["crops"]
    result, _ = run_tool("what_can_i_sow", {"month": "next month"}, None)
    assert result["month"] == "December"


def test_can_i_sow_today(fixed_today):
    fixed_today(2026, 11, 2)
    _, state = run_tool("select_topic", {"topic": "cotton", "name_said": "cotton"}, None)
    result, _ = run_tool("get_crop_timing", {"kind": "sowing", "when": "today"}, state)
    assert result["check"]["can_sow"] is False and "Wheat" in result["other_crops_this_month"]
    _, state = run_tool("select_topic", {"topic": "wheat", "name_said": "wheat"}, None)
    result, _ = run_tool("get_crop_timing", {"kind": "sowing", "when": "today"}, state)
    assert result["check"]["can_sow"] is True


def test_windows_wrap_and_mid():
    assert month_in_windows(1, parse_windows("December to February"))
    assert not month_in_windows(6, parse_windows("December to February"))
    assert parse_windows("Mid October to 20 November") == [((10, 15), (11, 20))]
    assert parse_windows("100 to 120 Days") == []


def test_declarations_enums_match_data():
    decls = {d["name"]: d for d in declarations()}
    topic_enum = decls["select_topic"]["parameters"]["properties"]["topic"]["enum"]
    assert set(data.topics()) <= set(topic_enum) and "other" in topic_enum
