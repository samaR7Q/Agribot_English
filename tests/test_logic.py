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


def test_topic_switch_asks_then_switches_on_yes():
    _, state = run_tool("select_topic", {"topic": "wheat", "name_said": "wheat"}, None)
    result, state = run_tool("select_topic", {"topic": "maize", "name_said": "maize"}, state)
    assert result["status"] == "confirm_switch" and state["topic"] == "wheat"
    assert "Wheat" in result["instruction"] and "Maize" in result["instruction"]
    result, state = run_tool("confirm_switch", {"accepted": True}, state)
    assert result["status"] == "switched" and state["topic"] == "maize"


def test_topic_switch_no_keeps_old_topic():
    _, state = run_tool("select_topic", {"topic": "wheat", "name_said": "wheat"}, None)
    _, state = run_tool("select_topic", {"topic": "cow", "name_said": "cow"}, state)
    result, state = run_tool("confirm_switch", {"accepted": False}, state)
    assert result["status"] == "kept" and state["topic"] == "wheat" and state["pending_switch"] is None


def test_unsupported_crop_lists_covered_topics():
    result, state = run_tool("select_topic", {"topic": "other", "name_said": "tomato"}, None)
    assert result["status"] == "unsupported" and "tomato" in result["instruction"]
    assert "Wheat" in result["instruction"] and state["topic"] is None


def test_info_without_topic_asks_for_crop():
    result, _ = run_tool("get_topic_info", {"aspect": "fertilizer", "question": "which fertilizer"}, None)
    assert result["status"] == "missing_info" and result["fields"] == ["topic"]


def test_varieties_probe_district_and_land_once():
    _, state = run_tool("select_topic", {"topic": "wheat", "name_said": "wheat"}, None)
    result, state = run_tool("get_topic_info", {"aspect": "varieties", "question": "best variety"}, state)
    assert result["status"] == "missing_info" and result["fields"] == ["district", "farm_type"]
    # Farmer ignored the question: the second call must not probe again.
    result, state = run_tool("get_topic_info", {"aspect": "varieties", "question": "best variety"}, state)
    assert result["status"] in ("ok", "no_info")


def test_rice_varieties_skip_land_type():
    _, state = run_tool("select_topic", {"topic": "rice", "name_said": "rice"}, None)
    result, _ = run_tool("get_topic_info", {"aspect": "varieties", "question": "variety"}, state)
    assert result["fields"] == ["district"]


def test_livestock_health_probes_age_and_weight():
    _, state = run_tool("select_topic", {"topic": "buffalo", "name_said": "bhains"}, None)
    result, _ = run_tool("get_topic_info", {"aspect": "health", "question": "fever"}, state)
    assert result["fields"] == ["animal_age", "animal_weight_kg"]


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


def test_mandi_needs_district_and_never_changes_topic():
    _, state = run_tool("select_topic", {"topic": "wheat", "name_said": "wheat"}, None)
    result, state = run_tool("get_mandi_rate", {"commodity": "maize"}, state)
    assert result["status"] == "missing_info" and result["fields"] == ["district"]
    result, state = run_tool("get_mandi_rate", {"commodity": "maize", "district": "multan"}, state)
    assert result["status"] == "ok" and result["rates"][0]["name"] == "Maize"
    assert state["topic"] == "wheat" and state["district"] is None   # asked city is not saved


def test_mandi_rice_gives_both_types_and_unknown_commodity():
    result, _ = run_tool("get_mandi_rate", {"commodity": "rice", "district": "Lahore"}, None)
    assert [r["name"] for r in result["rates"]] == ["Basmati paddy", "IRRI-6 paddy"]
    result, _ = run_tool("get_mandi_rate", {"commodity": "unknown"}, None)
    assert result["fields"] == ["commodity"]
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
