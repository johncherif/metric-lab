import json
from pathlib import Path

import pytest

from metric_lab.scoring import (Flag, calibration, calibration_message, match_flag, score_decision,
                                score_flags, score_sorting, word_count)

TRAPS = [
    {"id": "t_base", "charts": ["rate", "impressions"], "weeks": [5, 12], "issue": "base_changed"},
    {"id": "t_guard", "charts": ["optout"], "weeks": [5, 12], "issue": "guardrail"},
]


def f(chart, a, b, issue, conf=80):
    return Flag(chart, (a, b), issue, conf)


# ---------------- Stage 2: matching
def test_exact_match_is_correct():
    r = score_flags([f("rate", 5, 12, "base_changed")], TRAPS)
    assert r["scored"][0]["outcome"] == "correct" and r["detected"] == 1


def test_right_place_wrong_issue_is_partial():
    r = score_flags([f("rate", 6, 9, "novelty")], TRAPS)
    assert r["scored"][0]["outcome"] == "partial" and r["partial"] == 1


def test_wrong_chart_is_false_alarm():
    r = score_flags([f("plans", 5, 12, "base_changed")], TRAPS)
    assert r["scored"][0]["outcome"] == "false_alarm"


def test_alternate_chart_for_same_trap_counts():
    r = score_flags([f("impressions", 5, 8, "base_changed")], TRAPS)
    assert r["scored"][0]["outcome"] == "correct"


def test_shotgun_flag_over_whole_range_does_not_match():
    # weeks 1-12 overlaps the trap (5-12) but only 8/12 = 67% inside -> still matches;
    # weeks 1-12 on a trap of weeks 10-12 would be 3/12 = 25% -> must not match
    narrow = [{"id": "n", "charts": ["rate"], "weeks": [10, 12], "issue": "base_changed"}]
    assert match_flag(f("rate", 1, 12, "base_changed"), narrow)[0] is None


def test_reversed_week_range_is_normalized():
    r = score_flags([f("rate", 12, 5, "base_changed")], TRAPS)
    assert r["scored"][0]["outcome"] == "correct"


def test_duplicate_flags_count_once():
    r = score_flags([f("rate", 5, 12, "base_changed"), f("impressions", 6, 10, "base_changed")], TRAPS)
    assert [s["outcome"] for s in r["scored"]] == ["correct", "duplicate"]
    assert r["detected"] == 1 and r["false_alarms"] == 0


def test_later_correct_flag_upgrades_earlier_partial():
    r = score_flags([f("rate", 5, 12, "novelty"), f("rate", 5, 12, "base_changed")], TRAPS)
    assert [s["outcome"] for s in r["scored"]] == ["duplicate", "correct"]
    assert r["detected"] == 1 and r["partial"] == 0


def test_missed_traps_are_listed():
    r = score_flags([f("rate", 5, 12, "base_changed")], TRAPS)
    assert [t["id"] for t in r["missed"]] == ["t_guard"]
    assert r["score"] == pytest.approx(0.5)


def test_no_flags():
    r = score_flags([], TRAPS)
    assert r["score"] == 0 and len(r["missed"]) == 2


def test_overlapping_traps_prefer_same_issue_type():
    traps = [{"id": "a", "charts": ["c"], "weeks": [1, 6], "issue": "novelty"},
             {"id": "b", "charts": ["c"], "weeks": [4, 12], "issue": "base_changed"}]
    trap, _ = match_flag(f("c", 4, 6, "base_changed"), traps)
    assert trap["id"] == "b"


# ---------------- Calibration
def test_calibration_none_without_flags():
    assert calibration([]) is None
    assert "did not submit" in calibration_message(None)


def test_calibration_detects_overconfidence():
    r = score_flags([f("plans", 1, 3, "novelty", 90), f("rate", 5, 12, "base_changed", 90)], TRAPS)
    cal = calibration(r["scored"])
    assert cal["overconfident_misses"] == 1 and cal["bias"] > 0.3
    assert "at least 80% sure on 1 flag" in calibration_message(cal)


def test_calibration_ignores_duplicates():
    r = score_flags([f("rate", 5, 12, "base_changed", 100), f("rate", 5, 12, "base_changed", 50)], TRAPS)
    assert calibration(r["scored"])["n"] == 1


# ---------------- Stage 1 and 3
def test_sorting_unanswered_counts_wrong():
    metrics = [{"name": "a", "role": "success", "feedback": ""}, {"name": "b", "role": "vanity", "feedback": ""}]
    r = score_sorting({"a": "success"}, metrics)
    assert r["n_correct"] == 1 and r["score"] == 0.5


def test_decision_scoring_and_irrelevant_evidence():
    cfg = {"options": {"iterate": {"score": 1, "feedback": "ok"}},
           "required_evidence": ["e1", "e2"],
           "evidence": [{"id": "e1", "relevant": True}, {"id": "e2", "relevant": True},
                        {"id": "x", "relevant": False}]}
    r = score_decision("iterate", ["e1", "x"], cfg)
    assert r["decision_score"] == 1 and r["required_cited"] == 1 and r["irrelevant_cited"] == ["x"]


def test_word_count_ignores_punctuation():
    assert word_count("Iterate , because - the base changed!") == 5


# ---------------- Content integrity: every scenario file is internally consistent
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("path", sorted((ROOT / "content").glob("scenario*.json")))
def test_scenario_content_is_consistent(path):
    sc = json.loads(path.read_text())
    key = json.loads((ROOT / "data" / f"{sc['id']}_key.json").read_text())
    common = json.loads((ROOT / "content" / "common.json").read_text())
    chart_ids = {c["id"] for c in sc["charts"]}
    trap_ids = {t["id"] for t in key["traps"]}
    for t in key["traps"]:
        assert set(t["charts"]) <= chart_ids, f"trap {t['id']} points at a missing chart"
        assert t["issue"] in common["issue_types"]
    assert set(sc["support"]["walkthrough_traps"]) <= trap_ids
    assert set(sc["support"]["highlight_traps"]) <= trap_ids
    assert set(sc["hints"]) <= trap_ids
    assert {m["role"] for m in sc["metrics"]} <= set(common["roles"])
    ev_ids = {e["id"] for e in sc["decision"]["evidence"]}
    assert set(sc["decision"]["required_evidence"]) <= ev_ids
    assert set(sc["decision"]["options"]) == set(common["decisions"])
    assert max(o["score"] for o in sc["decision"]["options"].values()) == 1.0


# ---------------- Chart selection -> week range
from metric_lab.charts import weeks_from_selection


def test_box_edges_round_to_nearest_week():
    assert weeks_from_selection({"box": [{"x": [5.1, 12.4]}], "points": [{"x": 6}]}) == (5, 12)


def test_box_is_clamped_to_weeks_1_to_12():
    assert weeks_from_selection({"box": [{"x": [-3, 40]}], "points": []}) == (1, 12)


def test_clicked_points_used_when_no_box():
    assert weeks_from_selection({"box": [], "points": [{"x": 9}, {"x": 7}]}) == (7, 9)


def test_empty_selection_returns_none():
    assert weeks_from_selection({"box": [], "points": []}) is None
    assert weeks_from_selection(None) is None


def test_single_flag_calibration_is_not_overinterpreted():
    r = score_flags([f("rate", 5, 12, "base_changed", 70)], TRAPS)
    assert "not enough evidence" in calibration_message(calibration(r["scored"]))
