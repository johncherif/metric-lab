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


def _key(sid):
    return json.loads((ROOT / "data" / f"{sid}_key.json").read_text())["traps"]


@pytest.mark.parametrize("sc", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_full_scenario_flow(sc):
    sid = sc["id"]
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    at.sidebar.radio(key="page").set_value(sc["title"]).run()
    _btn(at, f"{sid}_go_metrics").click().run()

    # Stage 1: answer every metric with its correct role (shuffled order is handled by label)
    roles = {m["name"]: m["role"] for m in sc["metrics"]}
    for r in at.radio:
        if r.key and r.key.startswith(f"{sid}_m_"):
            r.set_value(roles[r.label])
    at.run()
    _btn(at, f"{sid}_check").click().run()
    assert not at.exception
    assert any("12 of 12" in m.value for m in at.metric)
    _btn(at, f"{sid}_go_dash").click().run()
    assert not at.exception

    # Stage 2: add one correct flag per trap, plus one false alarm and one duplicate
    traps = _key(sid)
    flags = [(t["charts"][0], tuple(t["weeks"]), t["issue"], 90) for t in traps]
    # a false alarm: the first chart/week span that no trap covers
    clear = next((c["id"], (w, w)) for c in sc["charts"] for w in range(1, 13)
                 if not any(c["id"] in t["charts"] and t["weeks"][0] <= w <= t["weeks"][1] for t in traps))
    flags.append((clear[0], clear[1], "novelty", 90))
    t0 = traps[0]
    flags.append((t0["charts"][-1], tuple(t0["weeks"]), t0["issue"], 60))
    for chart, weeks, issue, conf in flags:
        at.selectbox(key=f"{sid}_f_chart").set_value(chart)
        at.selectbox(key=f"{sid}_f_w0").set_value(weeks[0])
        at.selectbox(key=f"{sid}_f_w1").set_value(weeks[1])
        at.selectbox(key=f"{sid}_f_issue").set_value(issue)
        at.slider(key=f"{sid}_f_conf").set_value(conf)
        at.run()
        _btn(at, f"{sid}_add").click().run()
        assert not at.exception
    # adding without an issue type is rejected
    _btn(at, f"{sid}_add").click().run()
    assert any("Choose an issue type" in w.value for w in at.warning)

    if sc["support"]["hints"]:
        hint_keys = [b.key for b in at.button if b.key == f"{sid}_hint"]
        if hint_keys:
            _btn(at, f"{sid}_hint").click().run()
            assert at.info

    _btn(at, f"{sid}_submit").click().run()
    assert not at.exception
    assert any(f"{len(traps)} of {len(traps)}" in m.value for m in at.metric)
    assert any("Duplicate" in m.value for m in list(at.info) + list(at.warning))
    assert any("False alarm" in e.value for e in at.error)
    _btn(at, f"{sid}_go_dec").click().run()

    # Stage 3: validation first, then a full answer
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
    for i in range(4):
        at.radio(key=f"{sid}_rub_{i}").set_value(3)
    at.run()
    _btn(at, f"{sid}_rub_save").click().run()
    assert not at.exception
    assert any(m.label == "Decision" for m in at.metric)

    # The log captured the whole run
    events = at.session_state["events"]
    kinds = {e["event"] for e in events}
    assert {"sort_checked", "flag_added", "flags_submitted", "decision_submitted",
            "self_assessment"} <= kinds

    # Restart clears the scenario
    _btn(at, f"{sid}_restart").click().run()
    assert not at.exception
    assert any(b.key == f"{sid}_go_metrics" for b in at.button)


def test_submit_with_no_flags_requires_confirmation():
    sc = SCENARIOS[0]
    sid = sc["id"]
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.sidebar.radio(key="page").set_value(sc["title"]).run()
    at.session_state[f"sc_{sid}"]["stage"] = "dashboard"
    at.run()
    assert _btn(at, f"{sid}_submit").disabled
    at.checkbox(key=f"{sid}_none_ok").check().run()
    _btn(at, f"{sid}_submit").click().run()
    assert not at.exception
    assert any("did not submit any flags" in m.value for m in at.markdown)
