"""Metric Lab: JT FlexBuy Launch Review. Entry point for Streamlit.

Run locally:  streamlit run streamlit_app.py
"""
from __future__ import annotations

import random
import time
from functools import partial

import pandas as pd
import streamlit as st

from metric_lab import content as C
from metric_lab import scoring as S
from metric_lab.charts import figure, weeks_from_selection
from metric_lab.logger import log, to_csv

st.set_page_config(page_title="Metric Lab: JT FlexBuy Launch Review", layout="wide")

COMMON = C.common()
ROLES, ISSUES, DECISIONS = COMMON["roles"], COMMON["issue_types"], COMMON["decisions"]
ROLE_NOUNS = COMMON["role_nouns"]   # "This is a guardrail." reads better than the full option label
CONF_LEVELS = COMMON["confidence_levels"]
MIN_WORDS = 25
HINT_UNLOCK_SECONDS = 120           # help-seeking: try first, then ask
STAGES = ["brief", "metrics", "dashboard", "decision", "summary"]
STAGE_LABELS = ["Briefing", "Choose and define metrics", "Read the dashboard", "Decide and justify", "Summary"]


# ------------------------------------------------------------------ state helpers
def state(sid: str) -> dict:
    return st.session_state.setdefault(f"sc_{sid}", {
        "stage": "brief", "sort": None, "define": None, "flags": [], "flag_result": None, "hints": [],
        "sel_ver": 0, "decision": None, "self_ratings": None, "next_flag_id": 0,
        "first_impression": None, "retrieval": None, "coverage": None,
        "stage_t0": time.time(), "times": {},
    })


def go(sid: str, stage: str) -> None:
    """Move to a stage and record time spent in the previous one (time on task, for the evaluation)."""
    stt = state(sid)
    spent = round(time.time() - stt.get("stage_t0", time.time()), 1)
    stt["times"][stt["stage"]] = stt["times"].get(stt["stage"], 0) + spent
    log(sid, stt["stage"], "stage_time", seconds=spent)
    stt["stage"], stt["stage_t0"] = stage, time.time()
    log(sid, stage, "stage_enter")


def reset_scenario(sid: str) -> None:
    for k in [k for k in st.session_state if k.startswith(f"{sid}_") or k == f"sc_{sid}"]:
        del st.session_state[k]
    log(sid, "brief", "scenario_restart")


def shuffled(items: list, seed: str) -> list:
    """Stable shuffle, so content authored in grouped order is not shown grouped."""
    out = list(items)
    random.Random(seed).shuffle(out)
    return out


def plain(text: str) -> str:
    """Undo markdown escaping for widgets that show plain text (select boxes)."""
    return text.replace("\\$", "$")


def glossary_expander(where=st) -> None:
    exp = where.expander("Glossary")   # pre-training: key terms available before and during the scenarios
    for term, meaning in COMMON["glossary"].items():
        exp.markdown(f"**{term}:** {C.md(meaning)}")


# ------------------------------------------------------------------ sidebar
def sidebar() -> str:
    st.sidebar.markdown("## Metric Lab")
    st.sidebar.caption("Launch review simulator. JT Morgan, JT FlexBuy, and all data are fictional.")
    pages = ["Start here"] + [s["title"] for s in C.scenarios()] + ["My results"]
    page = st.sidebar.radio("Go to", pages, key="page")
    st.sidebar.divider()
    for s in C.scenarios():
        stg = state(s["id"])["stage"]
        done = stg == "summary"
        st.sidebar.markdown(f"{'**Done**' if done else STAGE_LABELS[STAGES.index(stg)]} · {s['title'].split(':')[0]}")
    st.sidebar.divider()
    glossary_expander(st.sidebar)
    st.sidebar.caption("Progress is kept only while this browser tab is open. "
                       "Download your activity log before closing the tab.")
    st.sidebar.download_button("Download activity log (CSV)", to_csv(), "metric_lab_log.csv",
                               "text/csv", key="dl_sidebar")
    return page


# ------------------------------------------------------------------ start page
def start_page() -> None:
    st.title("Metric Lab: JT FlexBuy Launch Review")
    st.write("You are an analyst at **JT Morgan**, a fictional bank that has launched **JT FlexBuy**, a buy now, "
             "pay later feature in its mobile app. Leadership wants to know whether the launch is working. In three "
             "short scenarios, you will choose and define the right metrics, read a dashboard of launch data, and "
             "make a recommendation, the way a real launch review works.")
    st.write("Reading data well is a skill built through practice, not a talent you either have or do not. "
             "This is a low-stakes place to practice it.")
    st.subheader("The three JT FlexBuy products")
    st.table(pd.DataFrame([
        ["JT FlexBuy", C.md("$50 to $499.99"), "4 monthly installments", "0% interest, no fee"],
        ["JT FlexBuy Plus", C.md("$500 and above"), "4 monthly installments", "0% interest, 4.5% fee"],
        ["JT FlexBuy Plan", C.md("$500 and above"), "6, 12, or 24 monthly installments",
         "Fixed interest rate (illustrative 15.99% APR)"],
    ], columns=["Product", "Purchase size", "Structure", "Cost to customer"]).set_index("Product"))
    st.caption("All product terms are illustrative and do not describe any real institution's products.")

    st.subheader("The measurement flywheel: adoption, engagement, value")
    st.write("- **Adoption:** are eligible customers trying it?\n"
             "- **Engagement:** do they come back?\n"
             "- **Value:** does it create real value for the bank and the customer, net of losses?\n\n"
             "Each turn of the flywheel feeds the next: customers who adopt can engage, and engaged customers "
             "create value. A problem at any stage slows the whole wheel.")
    st.write("Within each stage, metrics play one of three roles:")
    st.write("- **Success metrics** tell you whether the feature is working.\n"
             "- **Guardrails** must not get worse while you chase success.\n"
             "- **Vanity metrics** look impressive but do not support a decision.")

    st.subheader("How each scenario works")
    st.write("1. **Choose and define metrics:** sort candidate metrics into success, guardrail, or vanity, then "
             "build one metric yourself.\n"
             "2. **Read the dashboard:** flag anything misleading, say what kind of issue it is, and rate how "
             "confident you are. Some charts have nothing wrong with them.\n"
             "3. **Decide and justify:** recommend ship, iterate, or roll back, then compare your reasoning with "
             "an expert's.")
    st.info("Support fades as you go. Scenario 1 is a worked example, Scenario 2 offers hints after you try "
            "first, and Scenario 3 leaves you on your own. Plan on 10 to 30 minutes per scenario.")
    c1, c2 = st.columns(2)
    with c1:
        with st.expander("Issue types you can flag"):
            for label in ISSUES.values():
                st.write(f"- {label}")
    with c2:
        glossary_expander()


# ------------------------------------------------------------------ stage: brief
def stage_brief(sc: dict) -> None:
    sid, stt = sc["id"], state(sc["id"])
    b = sc["briefing"]
    with st.container(border=True):
        st.markdown(f"**From:** {b['from']}  \n**Subject:** {b['subject']}")
        for para in b["body"]:
            st.write(para)
    st.markdown(f"**Why this matters:** {sc['why_it_matters']}")
    st.markdown("**In this scenario you will:**")
    st.write("\n".join(f"- {o}" for o in sc["objectives"]))
    st.caption(f"Support level: **{sc['support']['label']}**. {sc['support']['description']}")

    # Productive failure: commit to a first impression before any guidance; revisited in the summary.
    fi = sc["first_impression"]
    st.subheader("Your first impression")
    impression = st.radio(fi["question"], list(fi["options"]), format_func=fi["options"].get, index=None,
                          key=f"{sid}_fi", disabled=stt["first_impression"] is not None)

    # Retrieval practice from earlier scenarios (testing effect; Gagne's "stimulate recall").
    ready_retrieval = True
    if sc.get("retrieval"):
        st.subheader("Quick recall check")
        st.caption("Two questions on what earlier scenarios covered. Recalling helps you remember.")
        answers = []
        for i, q in enumerate(sc["retrieval"]):
            answers.append(st.radio(q["q"], list(range(len(q["options"]))), index=None,
                                    format_func=lambda k, q=q: q["options"][k], key=f"{sid}_rq_{i}",
                                    disabled=stt["retrieval"] is not None))
        if stt["retrieval"] is None:
            ready_retrieval = False
            if st.button("Check my recall", key=f"{sid}_rq_check"):
                if any(a is None for a in answers):
                    st.warning("Answer both questions first.")
                else:
                    stt["retrieval"] = S.score_retrieval(answers, sc["retrieval"])
                    log(sid, "brief", "retrieval_checked", n_correct=stt["retrieval"]["n_correct"],
                        answers=answers)
                    st.rerun()
        else:
            for r in stt["retrieval"]["results"]:
                (st.success if r["correct"] else st.error)(
                    ("Correct. " if r["correct"] else f"Not quite: the answer is \"{r['answer_text']}\". ") + r["why"])
            ready_retrieval = True

    if st.button("Start: choose the metrics", type="primary", key=f"{sid}_go_metrics"):
        if impression is None:
            st.warning("Choose a first impression before you start. There is no wrong answer here.")
        elif not ready_retrieval:
            st.warning("Check your recall answers before you start.")
        else:
            stt["first_impression"] = impression
            log(sid, "brief", "first_impression", choice=impression)
            go(sid, "metrics")
            st.rerun()


# ------------------------------------------------------------------ stage: metrics (+ define it)
def stage_metrics(sc: dict) -> None:
    sid, stt = sc["id"], state(sc["id"])
    st.write(f"Leadership wants to know whether **{sc['layer'].lower()}** is on track. "
             "Sort each candidate metric into the role it should play in this launch review.")
    checked = stt["sort"] is not None
    metrics = shuffled(sc["metrics"], sid)
    answers = {}
    for i, m in enumerate(metrics):
        answers[m["name"]] = st.radio(
            m["name"], list(ROLES), format_func=ROLES.get, index=None, horizontal=True,
            key=f"{sid}_m_{i}", disabled=checked)
        if checked:
            r = next(r for r in stt["sort"]["results"] if r["name"] == m["name"])
            msg = (f"Correct: {ROLES[r['correct_role']]}. " if r["correct"]
                   else f"Not quite. This is a **{ROLE_NOUNS[r['correct_role']]}**. ") + r["feedback"]
            (st.success if r["correct"] else st.error)(msg)
    if not checked:
        n_missing = sum(v is None for v in answers.values())
        if st.button("Check my answers", type="primary", key=f"{sid}_check"):
            if n_missing:
                st.warning(f"Sort all metrics before checking ({n_missing} left).")
            else:
                stt["sort"] = S.score_sorting(answers, sc["metrics"])
                log(sid, "metrics", "sort_checked", score=stt["sort"]["score"], answers=answers)
                st.rerun()
        return
    st.metric("Metrics sorted correctly", f"{stt['sort']['n_correct']} of {stt['sort']['n_total']}")
    st.caption("Your first answers are the ones recorded, so the feedback above is for learning, not for retrying.")
    _define_it(sc)


def _define_it(sc: dict) -> None:
    """Build a metric from parts: practice in constructing, not only recognizing, a metric."""
    sid, stt = sc["id"], state(sc["id"])
    d = sc["define_it"]
    st.subheader(f"Define it: {d['metric']}")
    st.write(f"Build this metric yourself. It should answer: *{d['intent']}*")
    done = stt["define"] is not None
    choices = {}
    cols = st.columns(len(d["parts"]))
    for col, (key, part) in zip(cols, d["parts"].items()):
        opts = shuffled(list(part["options"]), f"{sid}_{key}")
        choices[key] = col.selectbox(plain(part["label"]), opts, index=None, format_func=plain,
                                     placeholder="Choose", key=f"{sid}_def_{key}", disabled=done)
    guardrail = st.text_input(d["guardrail_prompt"], key=f"{sid}_def_guard", disabled=done)
    if not done:
        if st.button("Check my metric", type="primary", key=f"{sid}_def_check"):
            if any(v is None for v in choices.values()) or len(guardrail.strip()) < 3:
                st.warning("Choose all three parts and name a guardrail first.")
            else:
                stt["define"] = S.score_definition(choices, d) | {"guardrail": guardrail}
                log(sid, "metrics", "definition_checked", choices=choices, guardrail=guardrail,
                    n_correct=stt["define"]["n_correct"])
                st.rerun()
        return
    for p in stt["define"]["parts"]:
        (st.success if p["correct"] else st.error)(
            f"**{plain(p['label'])}:** {p['chosen']}. " +
            ("" if p["correct"] else f"A better choice is \"{p['correct_option']}\". ") + p["feedback"])
    st.markdown("**Guardrails an expert might name** (compare with yours):")
    st.write("\n".join(f"- {g}" for g in d["model_guardrails"]))
    if st.button("Continue to the dashboard", type="primary", key=f"{sid}_go_dash"):
        go(sid, "dashboard")
        st.rerun()


# ------------------------------------------------------------------ stage: dashboard
def _on_chart_select(sid: str, chart_id: str, key: str) -> None:
    sel = st.session_state.get(key, {}).get("selection")
    weeks = weeks_from_selection(sel)
    if weeks:
        st.session_state[f"{sid}_f_chart"] = chart_id
        st.session_state[f"{sid}_f_w0"], st.session_state[f"{sid}_f_w1"] = weeks
        log(sid, "dashboard", "chart_selection", chart=chart_id, weeks=weeks)


def _add_flag(sid: str) -> None:
    stt = state(sid)
    issue = st.session_state.get(f"{sid}_f_issue")
    conf = st.session_state.get(f"{sid}_f_conf")
    if not issue or conf is None:
        st.session_state[f"{sid}_f_error"] = "Choose an issue type and your confidence before adding the flag."
        return
    st.session_state.pop(f"{sid}_f_error", None)
    fl = S.Flag(st.session_state[f"{sid}_f_chart"], (st.session_state[f"{sid}_f_w0"], st.session_state[f"{sid}_f_w1"]),
                issue, conf, {"id": stt["next_flag_id"]})
    stt["next_flag_id"] += 1
    stt["flags"].append(fl)
    stt["sel_ver"] += 1                      # clears the box selection on every chart
    st.session_state[f"{sid}_f_issue"] = None
    st.session_state[f"{sid}_f_conf"] = None  # no default: confidence is an active choice for every flag
    log(sid, "dashboard", "flag_added", chart=fl.chart, weeks=fl.weeks, issue=fl.issue, confidence=fl.confidence)


def _remove_flag(sid: str, flag_id: int) -> None:
    stt = state(sid)
    stt["flags"] = [f for f in stt["flags"] if f.meta.get("id") != flag_id]
    log(sid, "dashboard", "flag_removed", flag_id=flag_id)


def _chart_alt(ch: dict, seg: str) -> str:
    names = ", ".join(s["label"] for s in ch["series"])
    return f"Line chart: {plain(ch['title'])}, weeks 1 to 12, for {seg}. Series: {names}."


def stage_dashboard(sc: dict) -> None:
    sid, stt = sc["id"], state(sc["id"])
    charts = {c["id"]: c for c in sc["charts"]}
    traps = C.traps(sid)
    result = stt["flag_result"]
    submitted = result is not None

    seg = st.radio("Show data for", sc["segments"], horizontal=True, key=f"{sid}_seg",
                   on_change=lambda: log(sid, "dashboard", "segment_changed",
                                         segment=st.session_state[f"{sid}_seg"]))
    if sc.get("segment_note"):
        st.caption(sc["segment_note"])

    if not submitted and sc["support"]["walkthrough_traps"]:
        with st.container(border=True):
            st.markdown("**Senior analyst walkthrough**")
            for tid in sc["support"]["walkthrough_traps"]:
                for i, step in enumerate(sc["walkthrough"][tid], 1):
                    st.write(f"{i}. {step}")

    shades: dict[str, list] = {cid: [] for cid in charts}
    if not submitted:
        for t in traps:
            if t["id"] in sc["support"]["highlight_traps"]:
                for cid in t["charts"]:
                    shades[cid].append((t["weeks"], "guide"))
    else:
        found = {s["trap_id"] for s in result["scored"] if s["outcome"] in ("correct", "partial")}
        for t in traps:
            shades[t["charts"][0]].append((t["weeks"], "found" if t["id"] in found else "missed"))

    if not submitted:
        st.caption("To flag something, drag a box across the weeks of interest on a chart (or click a point). "
                   "The flag form below fills in automatically, and you can adjust it there. Some charts may show "
                   "nothing unusual.")
    cols = st.columns(2)
    for i, (cid, ch) in enumerate(charts.items()):
        frame = C.chart_frame(sid, ch, seg)
        fig = figure(frame, ch, shades[cid])
        with cols[i % 2]:
            st.markdown(f"**{ch['title']}**")
            if submitted:
                st.plotly_chart(fig, key=f"{sid}_chart_{cid}_done", config={"displayModeBar": False},
                                alt=_chart_alt(ch, seg))
            else:
                key = f"{sid}_chart_{cid}_{stt['sel_ver']}"
                st.plotly_chart(fig, key=key, on_select=partial(_on_chart_select, sid, cid, key),
                                selection_mode=("box", "points"), config={"displayModeBar": False},
                                alt=_chart_alt(ch, seg))
            with st.expander("View as a table"):   # text alternative to the chart (UDL)
                st.dataframe(frame.set_index("week").round(4), width="stretch")
    st.download_button("Download this scenario's data (CSV)", C.data(sid).to_csv(index=False).encode(),
                       f"{sid}_data.csv", "text/csv", key=f"{sid}_dl_data",
                       help="Explore the raw weekly counts in your own tool, such as Excel, Tableau, or Power BI.",
                       on_click=lambda: log(sid, "dashboard", "data_downloaded"))

    if not submitted:
        _flag_builder(sc, charts)
        _hints(sc, traps)
        _submit_flags(sc, traps)
    else:
        _flag_review(sc, charts, traps, result)


def _flag_builder(sc: dict, charts: dict) -> None:
    sid, stt = sc["id"], state(sc["id"])
    st.subheader("Add a flag")
    st.session_state.setdefault(f"{sid}_f_chart", next(iter(charts)))
    st.session_state.setdefault(f"{sid}_f_w0", 1)
    st.session_state.setdefault(f"{sid}_f_w1", 12)
    c1, c2 = st.columns(2)
    with c1:
        st.selectbox("Chart", list(charts), format_func=lambda c: plain(charts[c]["title"]), key=f"{sid}_f_chart")
        w0, w1 = st.columns(2)
        w0.selectbox("From week", list(range(1, 13)), key=f"{sid}_f_w0")
        w1.selectbox("To week", list(range(1, 13)), key=f"{sid}_f_w1")
    with c2:
        st.selectbox("What kind of issue is it?", list(ISSUES), format_func=ISSUES.get, index=None,
                     placeholder="Choose an issue type", key=f"{sid}_f_issue")
        st.radio("How confident are you that this is a real issue?", CONF_LEVELS, index=None, horizontal=True,
                 format_func=lambda v: f"{v}%", key=f"{sid}_f_conf")
    st.button("Add flag", on_click=_add_flag, args=(sid,), key=f"{sid}_add")
    if err := st.session_state.get(f"{sid}_f_error"):
        st.warning(err)

    st.markdown(f"**Your flags ({len(stt['flags'])})**")
    if not stt["flags"]:
        st.caption("No flags yet.")
    for fl in stt["flags"]:
        a, b = st.columns([6, 1])
        a.write(f"{charts[fl.chart]['title']} · weeks {fl.weeks[0]}–{fl.weeks[1]} · "
                f"{ISSUES[fl.issue]} · {fl.confidence}% confident")
        b.button("Remove", key=f"{sid}_rm_{fl.meta['id']}", on_click=_remove_flag, args=(sid, fl.meta["id"]))


def _hints(sc: dict, traps: list[dict]) -> None:
    """Hints unlock only after a first attempt or two minutes of looking (help-seeking research:
    learners who grab every hint up front learn less), then target issues not yet found."""
    sid, stt = sc["id"], state(sc["id"])
    if not sc["support"]["hints"]:
        return
    pool = [t["id"] for t in traps
            if t["id"] in sc["hints"] and t["id"] not in sc["support"]["walkthrough_traps"]]
    found = {s["trap_id"] for s in S.score_flags(stt["flags"], traps)["scored"] if s["outcome"] == "correct"}
    remaining = sorted((t for t in pool if t not in stt["hints"]), key=lambda t: t in found)
    for tid in stt["hints"]:
        st.info(f"Hint: {sc['hints'][tid]}")
    if not remaining:
        return
    waited = time.time() - stt.get("stage_t0", time.time())
    unlocked = bool(stt["flags"]) or waited >= HINT_UNLOCK_SECONDS
    if not unlocked:
        st.caption("Hints unlock after you add your first flag or spend two minutes with the dashboard. "
                   "Try first, then ask for help where you are stuck.")
        return
    if st.button(f"Show a hint ({len(remaining)} left)", key=f"{sid}_hint"):
        stt["hints"].append(remaining[0])
        log(sid, "dashboard", "hint_used", trap=remaining[0], seconds_on_dashboard=round(waited, 1),
            flags_before_hint=len(stt["flags"]))
        st.rerun()


def _submit_flags(sc: dict, traps: list[dict]) -> None:
    sid, stt = sc["id"], state(sc["id"])
    st.divider()
    confirm_empty = True
    if not stt["flags"]:
        confirm_empty = st.checkbox("I have reviewed the dashboard and found nothing worth flagging.",
                                    key=f"{sid}_none_ok")
    coverage = st.radio("How confident are you that you have found every issue on this dashboard?", CONF_LEVELS,
                        index=None, horizontal=True, format_func=lambda v: f"{v}%", key=f"{sid}_cov")
    if st.button("Submit my flags for review", type="primary", key=f"{sid}_submit", disabled=not confirm_empty):
        if coverage is None:
            st.warning("Rate how confident you are that you found every issue before submitting.")
            return
        res = S.score_flags(stt["flags"], traps)
        res["calibration"] = S.calibration(res["scored"])
        res["guided"] = S.split_guided(res, sc["support"]["walkthrough_traps"], traps)
        stt["flag_result"], stt["coverage"] = res, coverage
        for s in res["scored"]:
            fl = s["flag"]
            log(sid, "dashboard", "flag_scored", chart=fl.chart, weeks=fl.weeks, issue=fl.issue,
                confidence=fl.confidence, outcome=s["outcome"], trap=s["trap_id"],
                guided=s["trap_id"] in sc["support"]["walkthrough_traps"])
        log(sid, "dashboard", "flags_submitted", detected=res["detected"], partial=res["partial"],
            false_alarms=res["false_alarms"], missed=[t["id"] for t in res["missed"]],
            calibration=res["calibration"], coverage_confidence=coverage, guided=res["guided"],
            hints_used=stt["hints"])
        st.rerun()


OUTCOME_TEXT = {"correct": "Correct", "partial": "Right place, different issue",
                "false_alarm": "False alarm", "duplicate": "Duplicate of another flag"}


def _flag_review(sc: dict, charts: dict, traps: list[dict], res: dict) -> None:
    sid, stt = sc["id"], state(sc["id"])
    by_id = {t["id"]: t for t in traps}
    st.subheader("Review")
    a, b, c = st.columns(3)
    a.metric("Issues found", f"{res['detected']} of {res['n_traps']}")
    b.metric("Partly right", res["partial"])
    c.metric("False alarms", res["false_alarms"])
    g = res.get("guided")
    if g and g["guided_total"]:
        st.caption(f"Found on your own: {g['independent_found']} of {g['independent_total']}. "
                   f"Found with the walkthrough: {g['guided_found']} of {g['guided_total']}.")
    for s in res["scored"]:
        fl, out = s["flag"], s["outcome"]
        head = (f"**{OUTCOME_TEXT[out]}:** {charts[fl.chart]['title']}, weeks {fl.weeks[0]}–{fl.weeks[1]}, "
                f"{ISSUES[fl.issue]} ({fl.confidence}% confident).")
        if out in ("correct", "partial"):
            t = by_id[s["trap_id"]]
            extra = "" if out == "correct" else f" The issue here is: *{ISSUES[t['issue']]}*."
            (st.success if out == "correct" else st.warning)(f"{head}{extra} {t['explanation']}")
        elif out == "duplicate":
            t = by_id[s["trap_id"]]
            if fl.issue != t["issue"]:
                st.warning(head + " This covers an issue you already found, but with a different diagnosis. "
                           f"The issue here is: *{ISSUES[t['issue']]}*.")
            else:
                st.info(head + " This issue was already credited to another flag.")
        else:
            st.error(head + " Nothing misleading was planted here. Not every movement on a chart is a problem; "
                            "ask whether the change is larger than normal week-to-week noise.")
    for t in res["missed"]:
        st.error(f"**Missed: {t['title']}** ({charts[t['charts'][0]]['title']}, weeks "
                 f"{t['weeks'][0]}–{t['weeks'][1]}). {ISSUES[t['issue']]}. {t['explanation']}")
    st.markdown("**Confidence check**")
    st.write(S.calibration_message(res["calibration"]))
    if msg := S.coverage_message(stt.get("coverage"), res["detected"], res["n_traps"]):
        st.write(msg)
    with st.container(border=True):   # process-level feedback (Hattie & Timperley)
        st.markdown("**Checks to run on any dashboard**")
        st.write("\n".join(f"- {item}" for item in COMMON["process_checklist"]))
        st.caption(COMMON["mindset_note"])
    if st.button("Continue to the decision", type="primary", key=f"{sid}_go_dec"):
        go(sid, "decision")
        st.rerun()


# ------------------------------------------------------------------ stage: decision
def _findings_panel(sc: dict) -> None:
    """Carry the learner's own Stage 2 findings into the decision, so it is built on their evidence."""
    stt = state(sc["id"])
    res = stt["flag_result"]
    by_id = {t["id"]: t for t in C.traps(sc["id"])}
    found = [by_id[s["trap_id"]]["title"] for s in res["scored"] if s["outcome"] in ("correct", "partial")]
    missed = [t["title"] for t in res["missed"]]
    with st.container(border=True):
        st.markdown("**What the dashboard showed**")
        if found:
            st.write("You found:\n" + "\n".join(f"- {t}" for t in found))
        if missed:
            st.write("Revealed in the review:\n" + "\n".join(f"- {t}" for t in missed))


def stage_decision(sc: dict) -> None:
    sid, stt = sc["id"], state(sc["id"])
    d = sc["decision"]
    done = stt["decision"] is not None
    _findings_panel(sc)
    st.write(d["question"])
    choice = st.radio("Your recommendation", list(DECISIONS), format_func=DECISIONS.get, index=None,
                      key=f"{sid}_dec", disabled=done)
    st.markdown("**Which observations support your recommendation?** Select all that apply.")
    evidence = shuffled(d["evidence"], sid + "_ev")
    chosen = [e["id"] for e in evidence if st.checkbox(e["text"], key=f"{sid}_ev_{e['id']}", disabled=done)]
    if not done:
        text = st.text_area("Your rationale, as you would say it in the launch review", key=f"{sid}_rat",
                            height=150, placeholder="State your recommendation, the evidence for it, and what you "
                                                    "would monitor next.")
        n = S.word_count(text)
        st.caption(f"{n} words (at least {MIN_WORDS}). Word count updates when you click outside the box.")
        if st.button("Submit and compare with the expert", type="primary", key=f"{sid}_dec_submit"):
            problems = []
            if not choice:
                problems.append("choose a recommendation")
            if not chosen:
                problems.append("select at least one supporting observation")
            if n < MIN_WORDS:
                problems.append(f"write at least {MIN_WORDS} words")
            if problems:
                st.warning("Before submitting, please " + ", ".join(problems) + ".")
            else:
                stt["decision"] = S.score_decision(choice, chosen, d) | {"choice": choice, "text": text}
                log(sid, "decision", "decision_submitted", choice=choice, evidence=chosen, words=n, rationale=text,
                    **{k: v for k, v in stt["decision"].items() if k not in ("choice", "text", "decision_feedback")})
                st.rerun()
        return

    r = stt["decision"]
    st.subheader("How your decision compares")
    (st.success if r["decision_score"] == 1 else st.warning if r["decision_score"] > 0 else st.error)(
        r["decision_feedback"])
    st.write(f"You cited **{r['required_cited']} of {r['required_total']}** key observations.")
    by_id = {e["id"]: e for e in d["evidence"]}
    for eid in d["required_evidence"]:
        if eid not in chosen:
            st.info(f"Key observation you did not cite: {by_id[eid]['text']}")
    for eid in r["irrelevant_cited"]:
        st.info(f"You cited: \"{by_id[eid]['text']}\" {by_id[eid]['why']}")
    yours, expert = st.columns(2)
    with yours:
        st.markdown("**Your rationale**")
        with st.container(border=True):
            st.write(r["text"])
    with expert:
        st.markdown("**Expert rationale**")
        with st.container(border=True):
            st.write(d["expert_rationale"])

    st.subheader("Rate your own rationale")
    st.caption("Compare your rationale with the expert's, then choose the description that best fits yours. "
               "The same rubric is used to score the final transfer task. " + COMMON["rubric_note"])
    with st.expander("See an example rationale at each level"):   # exemplars convey quality (Sadler)
        for ex in sc["exemplars"]:
            st.write(f"- {ex}")
    ratings_done = stt["self_ratings"] is not None
    ratings = {}
    for i, crit in enumerate(COMMON["rubric"]):
        ratings[crit["criterion"]] = st.radio(
            crit["criterion"], [1, 2, 3, 4], index=None, key=f"{sid}_rub_{i}", disabled=ratings_done,
            format_func=lambda lv, c=crit: f"{lv}. {c['levels'][lv - 1]}")
    if not ratings_done and st.button("Save my self-assessment", type="primary", key=f"{sid}_rub_save"):
        if any(v is None for v in ratings.values()):
            st.warning("Rate all four criteria first.")
        else:
            stt["self_ratings"] = ratings
            log(sid, "decision", "self_assessment", **ratings)
            go(sid, "summary")
            st.rerun()


# ------------------------------------------------------------------ stage: summary
def stage_summary(sc: dict) -> None:
    sid, stt = sc["id"], state(sc["id"])
    fr, dr = stt["flag_result"], stt["decision"]
    st.subheader("Your results for this scenario")
    a, b, c, d = st.columns(4)
    a.metric("Metrics sorted", f"{stt['sort']['n_correct']}/{stt['sort']['n_total']}")
    a.metric("Metric built", f"{stt['define']['n_correct']}/{stt['define']['n_total']} parts")
    g = fr.get("guided") or {}
    if g.get("guided_total"):
        b.metric("Issues found on your own", f"{g['independent_found']}/{g['independent_total']}",
                 help=f"Plus {g['guided_found']} of {g['guided_total']} found with the walkthrough.")
    else:
        b.metric("Issues found", f"{fr['detected']}/{fr['n_traps']}",
                 help="Partly right flags and false alarms are listed on the dashboard review.")
    cal = fr["calibration"]
    c.metric("Confidence vs. accuracy", S.calibration_label(cal), help=S.calibration_message(cal))
    d.metric("Decision", DECISIONS[dr["choice"]].split(":")[0], help=dr["decision_feedback"])
    minutes = sum(stt["times"].values()) / 60
    st.write(f"Hints used: {len(stt['hints'])}. Time on this scenario: about {minutes:.0f} min. "
             f"Self-assessment total: {sum(stt['self_ratings'].values())} of 16.")
    if msg := S.self_assessment_check(stt["self_ratings"], dr["decision_score"], dr["evidence_score"]):
        st.info(msg)

    # Productive failure, consolidated: compare the first impression with the expert view.
    fi = sc["first_impression"]
    with st.container(border=True):
        st.markdown("**Before and after**")
        st.write(f"Before analyzing, you said: *{fi['options'].get(stt['first_impression'], 'no answer')}*.")
        st.write(f"After the analysis, the expert view is: {sc['expert_short']}")
        st.caption("What changed between your first impression and now is the part of this scenario most worth "
                   "remembering.")

    nxt = [s for s in C.scenarios() if s["order"] == sc["order"] + 1]
    if nxt:
        st.info(f"Next: **{nxt[0]['title']}**. Support will be lighter.")
        st.button(f"Go to {nxt[0]['title']}", type="primary", key=f"{sid}_next",
                  on_click=lambda t=nxt[0]["title"]: st.session_state.update(page=t))
    else:
        st.info("You have completed all scenarios. Download your activity log from the sidebar.")
    if st.button("Restart this scenario", key=f"{sid}_restart"):
        reset_scenario(sid)
        st.rerun()


# ------------------------------------------------------------------ scenario page
RENDER = {"brief": stage_brief, "metrics": stage_metrics, "dashboard": stage_dashboard,
          "decision": stage_decision, "summary": stage_summary}


def scenario_page(sc: dict) -> None:
    stt = state(sc["id"])
    st.title(sc["title"])
    idx = STAGES.index(stt["stage"])
    st.progress((idx + 1) / len(STAGES), text=f"Step {idx + 1} of {len(STAGES)}: {STAGE_LABELS[idx]}")
    RENDER[stt["stage"]](sc)


def results_page() -> None:
    st.title("My results")
    rows = []
    for sc in C.scenarios():
        stt = state(sc["id"])
        if stt["stage"] != "summary":
            rows.append([sc["title"], "In progress" if stt["stage"] != "brief" else "Not started", "", "", "", ""])
            continue
        fr = stt["flag_result"]
        rows.append([sc["title"], "Done", f"{stt['sort']['n_correct']}/{stt['sort']['n_total']}",
                     f"{stt['define']['n_correct']}/{stt['define']['n_total']}",
                     f"{fr['detected']}/{fr['n_traps']}", S.calibration_label(fr["calibration"])])
    st.table(pd.DataFrame(rows, columns=["Scenario", "Status", "Metrics sorted", "Metric built", "Issues found",
                                         "Confidence vs. accuracy"]).set_index("Scenario"))
    st.download_button("Download activity log (CSV)", to_csv(), "metric_lab_log.csv", "text/csv", key="dl_results")


def main() -> None:
    page = sidebar()
    if page == "Start here":
        start_page()
    elif page == "My results":
        results_page()
    else:
        scenario_page(next(s for s in C.scenarios() if s["title"] == page))


main()
