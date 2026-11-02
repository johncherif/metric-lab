"""End-to-end run through every scenario using Streamlit's AppTest harness."""
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "streamlit_app.py")
SCENARIOS = sorted((json.loads(p.read_text()) for p in (ROOT / "content").glob("scenario*.json")),
                   key=lambda s: s["order"])


def _btn(at, key):
    return next(b for b in at.button if b.key == key)


def _has_btn(at, key):
    return any(b.key == key for b in at.button)


def _key(sid):
    return json.loads((ROOT / "data" / f"{sid}_key.json").read_text())["traps"]


def _add_flag(at, sid, chart, weeks, issue, conf):
    at.selectbox(key=f"{sid}_f_chart").set_value(chart)
    at.selectbox(key=f"{sid}_f_w0").set_value(weeks[0])
    at.selectbox(key=f"{sid}_f_w1").set_value(weeks[1])
    at.selectbox(key=f"{sid}_f_issue").set_value(issue)
    at.radio(key=f"{sid}_f_conf").set_value(conf)
    at.run()
    _btn(at, f"{sid}_add").click().run()
    assert not at.exception


@pytest.mark.parametrize("sc", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_full_scenario_flow(sc):
    sid = sc["id"]
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    at.sidebar.radio(key="page").set_value(sc["title"]).run()

    # Briefing: objectives shown; first impression required; recall check required where present
    assert any("In this scenario you will" in m.value for m in at.markdown)
    _btn(at, f"{sid}_go_metrics").click().run()
    assert any("first impression" in w.value for w in at.warning)
    at.radio(key=f"{sid}_fi").set_value("mixed").run()
    if sc.get("retrieval"):
        _btn(at, f"{sid}_go_metrics").click().run()
        assert any("recall" in w.value for w in at.warning)
        for i, q in enumerate(sc["retrieval"]):
            at.radio(key=f"{sid}_rq_{i}").set_value(q["answer"])
        at.run()
        _btn(at, f"{sid}_rq_check").click().run()
        assert sum("Correct." in s.value for s in at.success) == len(sc["retrieval"])
    _btn(at, f"{sid}_go_metrics").click().run()
    assert not at.exception

    # Stage 1a: sort every metric correctly
    roles = {m["name"]: m["role"] for m in sc["metrics"]}
    for r in at.radio:
        if r.key and r.key.startswith(f"{sid}_m_"):
            r.set_value(roles[r.label])
    at.run()
    _btn(at, f"{sid}_check").click().run()
    assert any("12 of 12" in m.value for m in at.metric)

    # Stage 1b: Define it (one deliberate mistake on the denominator)
    d = sc["define_it"]
    for key, part in d["parts"].items():
        val = part["correct"]
        if key == "den":
            val = next(o for o in part["options"] if o != part["correct"])
        at.selectbox(key=f"{sid}_def_{key}").set_value(val)
    at.text_input(key=f"{sid}_def_guard").input("Opt-out rate, to make sure growth is not annoying customers").run()
    _btn(at, f"{sid}_def_check").click().run()
    assert not at.exception
    assert any("A better choice is" in e.value for e in at.error)
    assert sum(1 for s in at.success if s.value.startswith("**")) >= len(d["parts"]) - 1
    _btn(at, f"{sid}_go_dash").click().run()
    assert not at.exception

    # Stage 2: confidence has no default; flags; coverage required
    traps = _key(sid)
    at.selectbox(key=f"{sid}_f_issue").set_value(traps[0]["issue"]).run()
    _btn(at, f"{sid}_add").click().run()
    assert any("confidence" in w.value for w in at.warning)

    for t in traps:
        _add_flag(at, sid, t["charts"][0], tuple(t["weeks"]), t["issue"], 90)
    clear = next((c["id"], (w, w)) for c in sc["charts"] for w in range(1, 13)
                 if not any(c["id"] in t["charts"] and t["weeks"][0] <= w <= t["weeks"][1] for t in traps))
    _add_flag(at, sid, clear[0], clear[1], "novelty", 90)
    t0 = traps[0]
    _add_flag(at, sid, t0["charts"][-1], tuple(t0["weeks"]), t0["issue"], 60)
    assert at.radio(key=f"{sid}_f_conf").value is None          # reset after each flag

    if sc["support"]["hints"] and _has_btn(at, f"{sid}_hint"):  # unlocked after the first flag
        _btn(at, f"{sid}_hint").click().run()
        assert any(i.value.startswith("Hint:") for i in at.info)

    _btn(at, f"{sid}_submit").click().run()
    assert any("found every issue" in w.value for w in at.warning)
    at.radio(key=f"{sid}_cov").set_value(80).run()
    _btn(at, f"{sid}_submit").click().run()
    assert not at.exception
    assert any(f"{len(traps)} of {len(traps)}" in m.value for m in at.metric)
    assert any("Duplicate" in m.value for m in list(at.info) + list(at.warning))
    assert any("False alarm" in e.value for e in at.error)
    assert any("Checks to run on any dashboard" in m.value for m in at.markdown)
    assert any("sure you had found every issue" in m.value for m in at.markdown)
    if sc["support"]["walkthrough_traps"]:
        assert any("Found on your own" in c.value for c in at.caption)
    _btn(at, f"{sid}_go_dec").click().run()

    # Stage 3: findings panel, validation, full answer, exemplars, rubric
    assert any("What the dashboard showed" in m.value for m in at.markdown)
    _btn(at, f"{sid}_dec_submit").click().run()
    assert any("Before submitting" in w.value for w in at.warning)
    best = max(sc["decision"]["options"], key=lambda k: sc["decision"]["options"][k]["score"])
    at.radio(key=f"{sid}_dec").set_value(best)
    for eid in sc["decision"]["required_evidence"]:
        at.checkbox(key=f"{sid}_ev_{eid}").check()
    at.text_area(key=f"{sid}_rat").input(" ".join(["word"] * 30))
    at.run()
    _btn(at, f"{sid}_dec_submit").click().run()
    assert not at.exception
    assert any("expert" in s.value.lower() for s in at.success)
    assert any("SOLO" in c.value for c in at.caption)
    for i in range(4):
        at.radio(key=f"{sid}_rub_{i}").set_value(4)
    at.run()
    _btn(at, f"{sid}_rub_save").click().run()
    assert not at.exception
    assert any(m.label == "Decision" for m in at.metric)
    assert any("Before and after" in m.value for m in at.markdown)
    assert any("consistent" in i.value for i in at.info)       # full marks earned, top self-rating

    events = at.session_state["events"]
    kinds = {e["event"] for e in events}
    assert {"first_impression", "sort_checked", "definition_checked", "flag_added", "flags_submitted",
            "decision_submitted", "self_assessment", "stage_time"} <= kinds
    if sc.get("retrieval"):
        assert "retrieval_checked" in kinds

    nxt = [b for b in at.button if b.key == f"{sid}_next"]
    if nxt:
        nxt[0].click().run()
        assert at.sidebar.radio(key="page").value != sc["title"]
        at.sidebar.radio(key="page").set_value(sc["title"]).run()

    _btn(at, f"{sid}_restart").click().run()
    assert not at.exception
    assert _has_btn(at, f"{sid}_go_metrics")


def test_submit_with_no_flags_requires_confirmation():
    sc = SCENARIOS[0]
    sid = sc["id"]
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.sidebar.radio(key="page").set_value(sc["title"]).run()
    at.session_state[f"sc_{sid}"]["stage"] = "dashboard"
    at.run()
    assert _btn(at, f"{sid}_submit").disabled
    at.checkbox(key=f"{sid}_none_ok").check()
    at.radio(key=f"{sid}_cov").set_value(50).run()
    _btn(at, f"{sid}_submit").click().run()
    assert not at.exception
    assert any("did not submit any flags" in m.value for m in at.markdown)


def test_hints_locked_before_first_attempt():
    sc = SCENARIOS[1]
    sid = sc["id"]
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.sidebar.radio(key="page").set_value(sc["title"]).run()
    at.session_state[f"sc_{sid}"]["stage"] = "dashboard"
    at.run()
    assert not _has_btn(at, f"{sid}_hint")
    assert any("Hints unlock" in c.value for c in at.caption)


def test_start_page_uses_proposal_branding():
    at = AppTest.from_file(APP, default_timeout=30).run()
    text = " ".join(m.value for m in at.markdown)
    assert "JT Morgan" in text and "JT FlexBuy" in text and "Harborline" not in text
    assert "flywheel" in " ".join(h.value for h in at.subheader).lower()
