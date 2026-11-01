"""Metric Lab: BNPL Launch Review. Entry point for Streamlit.

Run locally:  streamlit run streamlit_app.py
"""
from __future__ import annotations

import random
from functools import partial

import pandas as pd
import streamlit as st

from metric_lab import content as C
from metric_lab import scoring as S
from metric_lab.charts import figure, weeks_from_selection
from metric_lab.logger import log, to_csv

st.set_page_config(page_title="Metric Lab: BNPL Launch Review", layout="wide")

COMMON = C.common()
ROLES, ISSUES, DECISIONS = COMMON["roles"], COMMON["issue_types"], COMMON["decisions"]
ROLE_NOUNS = COMMON["role_nouns"]   # "This is a guardrail." reads better than the full option label
MIN_WORDS = 25
STAGES = ["brief", "metrics", "dashboard", "decision", "summary"]
STAGE_LABELS = ["Briefing", "Choose metrics", "Read the dashboard", "Decide and justify", "Summary"]


# ------------------------------------------------------------------ state helpers
def state(sid: str) -> dict:
    return st.session_state.setdefault(f"sc_{sid}", {
        "stage": "brief", "sort": None, "flags": [], "flag_result": None, "hints": [],
        "sel_ver": 0, "decision": None, "self_ratings": None, "next_flag_id": 0,
    })


def go(sid: str, stage: str) -> None:
    state(sid)["stage"] = stage
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


# ------------------------------------------------------------------ sidebar
def sidebar() -> str:
    st.sidebar.markdown("## Metric Lab")
    st.sidebar.caption("BNPL launch review simulator. Harborline Bank and all data are fictional.")
    pages = ["Start here"] + [s["title"] for s in C.scenarios()] + ["My results"]
    page = st.sidebar.radio("Go to", pages, key="page")
    st.sidebar.divider()
    for s in C.scenarios():
        stg = state(s["id"])["stage"]
        done = stg == "summary"
        st.sidebar.markdown(f"{'**Done**' if done else STAGE_LABELS[STAGES.index(stg)]} · {s['title'].split(':')[0]}")
    st.sidebar.divider()
    st.sidebar.caption("Progress is kept only while this browser tab is open. "
                       "Download your activity log before closing the tab.")
    st.sidebar.download_button("Download activity log (CSV)", to_csv(), "metric_lab_log.csv",
                               "text/csv", key="dl_sidebar")
    return page


# ------------------------------------------------------------------ start page
def start_page() -> None:
    st.title("Metric Lab: BNPL Launch Review")
    st.write("You are an analyst at **Harborline Bank**, a fictional bank that has launched "
             "**Harborline Flex**, a buy now, pay later feature in its mobile app. "
             "Leadership wants to know whether the launch is working. In three short scenarios, "
             "you will choose the right metrics, read a dashboard of launch data, and make a "
             "recommendation, the way a real launch review works.")
    st.subheader("The three Flex products")
    st.table(pd.DataFrame([
        ["Flex 4", C.md("$50 to $499.99"), "4 monthly installments", "0% interest, no fee"],
        ["Flex 4 Plus", C.md("$500 and above"), "4 monthly installments", C.md("0% interest, flat $25 fee")],
        ["Flex Plan", C.md("$500 and above"), "6, 12, or 24 monthly installments", "Fixed APR (15.99%)"],
    ], columns=["Product", "Purchase size", "Structure", "Cost to customer"]).set_index("Product"))
    st.caption("All product terms are illustrative and do not describe any real institution's products.")

    st.subheader("How to measure a feature: adoption, engagement, value")
    st.write("- **Adoption:** are eligible customers trying it?\n"
             "- **Engagement:** do they come back?\n"
             "- **Value:** does it create real value for the bank and the customer, net of losses?")
    st.write("Within each layer, metrics play one of three roles:")
    st.write("- **Success metrics** tell you whether the feature is working.\n"
             "- **Guardrails** must not get worse while you chase success.\n"
             "- **Vanity metrics** look impressive but do not support a decision.")

    st.subheader("How each scenario works")
    st.write("1. **Choose metrics:** sort candidate metrics into success, guardrail, or vanity.\n"
             "2. **Read the dashboard:** flag anything misleading, say what kind of issue it is, "
             "and rate how confident you are.\n"
             "3. **Decide and justify:** recommend ship, iterate, or roll back, then compare your "
             "reasoning with an expert's.")
    st.info("Support fades as you go. Scenario 1 is a worked example, Scenario 2 offers hints "
            "on request, and Scenario 3 leaves you on your own. Plan on about 20 minutes per scenario.")
    with st.expander("Issue types you can flag"):
        for label in ISSUES.values():
            st.write(f"- {label}")


# ------------------------------------------------------------------ stage: brief
def stage_brief(sc: dict) -> None:
    b = sc["briefing"]
    st.markdown(f"**From:** {b['from']}  \n**Subject:** {b['subject']}")
    for para in b["body"]:
        st.write(para)
    st.caption(f"Support level: **{sc['support']['label']}**. {sc['support']['description']}")
    if st.button("Start: choose the metrics", type="primary", key=f"{sc['id']}_go_metrics"):
        go(sc["id"], "metrics")
        st.rerun()


# ------------------------------------------------------------------ stage: metrics
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
                log(sid, "metrics", "sort_checked", score=stt["sort"]["score"],
                    answers=answers)
                st.rerun()
    else:
        st.metric("Metrics sorted correctly", f"{stt['sort']['n_correct']} of {stt['sort']['n_total']}")
        st.caption("Your first answers are the ones recorded, so the feedback above is for learning, not for retrying.")
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
    if not issue:
        st.session_state[f"{sid}_f_error"] = "Choose an issue type before adding the flag."
        return
    st.session_state.pop(f"{sid}_f_error", None)
    fl = S.Flag(st.session_state[f"{sid}_f_chart"], (st.session_state[f"{sid}_f_w0"], st.session_state[f"{sid}_f_w1"]),
                issue, st.session_state[f"{sid}_f_conf"], {"id": stt["next_flag_id"]})
    stt["next_flag_id"] += 1
    stt["flags"].append(fl)
    stt["sel_ver"] += 1                      # clears the box selection on every chart
    st.session_state[f"{sid}_f_issue"] = None
    log(sid, "dashboard", "flag_added", chart=fl.chart, weeks=fl.weeks, issue=fl.issue,
        confidence=fl.confidence)


def _remove_flag(sid: str, flag_id: int) -> None:
    stt = state(sid)
    stt["flags"] = [f for f in stt["flags"] if f.meta.get("id") != flag_id]
    log(sid, "dashboard", "flag_removed", flag_id=flag_id)


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

    # Worked-example walkthrough (fades in later scenarios)
    if not submitted and sc["support"]["walkthrough_traps"]:
        with st.container(border=True):
            st.markdown("**Senior analyst walkthrough**")
            for tid in sc["support"]["walkthrough_traps"]:
                for i, step in enumerate(sc["walkthrough"][tid], 1):
                    st.write(f"{i}. {step}")

    # Shading: guidance before submission, found/missed after
    shades: dict[str, list] = {cid: [] for cid in charts}
    if not submitted:
        for t in traps:
            if t["id"] in sc["support"]["highlight_traps"]:
                for cid in t["charts"]:
                    shades[cid].append((t["weeks"], "guide"))
    else:
        found = {s["trap_id"] for s in result["scored"] if s["outcome"] in ("correct", "partial")}
        for t in traps:
            kind = "found" if t["id"] in found else "missed"
            shades[t["charts"][0]].append((t["weeks"], kind))

    if not submitted:
        st.caption("To flag something, drag a box across the weeks of interest on a chart (or click a "
                   "point). The flag form below fills in automatically, and you can adjust it there.")
    cols = st.columns(2)
    for i, (cid, ch) in enumerate(charts.items()):
        fig = figure(C.chart_frame(sid, ch, seg), ch, shades[cid])
        with cols[i % 2]:
            st.markdown(f"**{ch['title']}**")
            if submitted:
                st.plotly_chart(fig, key=f"{sid}_chart_{cid}_done", config={"displayModeBar": False})
            else:
                key = f"{sid}_chart_{cid}_{stt['sel_ver']}"
                st.plotly_chart(fig, key=key, on_select=partial(_on_chart_select, sid, cid, key),
                                selection_mode=("box", "points"),
                                config={"displayModeBar": False})

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
    st.session_state.setdefault(f"{sid}_f_conf", 70)
    c1, c2 = st.columns(2)
    with c1:
        st.selectbox("Chart", list(charts), format_func=lambda c: charts[c]["title"].replace("\\$", "$"),  # plain text, not markdown
                     key=f"{sid}_f_chart")
        w0, w1 = st.columns(2)
        w0.selectbox("From week", list(range(1, 13)), key=f"{sid}_f_w0")
        w1.selectbox("To week", list(range(1, 13)), key=f"{sid}_f_w1")
    with c2:
        st.selectbox("What kind of issue is it?", list(ISSUES), format_func=ISSUES.get, index=None,
                     placeholder="Choose an issue type", key=f"{sid}_f_issue")
        st.slider("How confident are you that this is a real issue?", 50, 100, step=10,
                  format="%d%%", key=f"{sid}_f_conf")
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
        b.button("Remove", key=f"{sid}_rm_{fl.meta['id']}", on_click=_remove_flag,
                 args=(sid, fl.meta["id"]))


def _hints(sc: dict, traps: list[dict]) -> None:
    sid, stt = sc["id"], state(sc["id"])
    if not sc["support"]["hints"]:
        return
    pool = [t["id"] for t in traps
            if t["id"] in sc["hints"] and t["id"] not in sc["support"]["walkthrough_traps"]]
    # Offer hints for issues the learner has not yet flagged first (support where it is needed),
    # instead of a fixed order that could spend a hint on an issue already found.
    found = {s["trap_id"] for s in S.score_flags(stt["flags"], traps)["scored"]
             if s["outcome"] == "correct"}
    remaining = sorted((t for t in pool if t not in stt["hints"]), key=lambda t: t in found)
    for tid in stt["hints"]:
        st.info(f"Hint: {sc['hints'][tid]}")
    if remaining and st.button(f"Show a hint ({len(remaining)} left)", key=f"{sid}_hint"):
        stt["hints"].append(remaining[0])
        log(sid, "dashboard", "hint_used", trap=remaining[0])
        st.rerun()


def _submit_flags(sc: dict, traps: list[dict]) -> None:
    sid, stt = sc["id"], state(sc["id"])
    st.divider()
    confirm_empty = True
    if not stt["flags"]:
        confirm_empty = st.checkbox("I have reviewed the dashboard and found nothing worth flagging.",
                                    key=f"{sid}_none_ok")
    if st.button("Submit my flags for review", type="primary", key=f"{sid}_submit",
                 disabled=not confirm_empty):
        res = S.score_flags(stt["flags"], traps)
        res["calibration"] = S.calibration(res["scored"])
        stt["flag_result"] = res
        for s in res["scored"]:
            fl = s["flag"]
            log(sid, "dashboard", "flag_scored", chart=fl.chart, weeks=fl.weeks, issue=fl.issue,
                confidence=fl.confidence, outcome=s["outcome"], trap=s["trap_id"])
        log(sid, "dashboard", "flags_submitted", detected=res["detected"], partial=res["partial"],
            false_alarms=res["false_alarms"], missed=[t["id"] for t in res["missed"]],
            calibration=res["calibration"], hints_used=stt["hints"])
        st.rerun()


OUTCOME_TEXT = {"correct": "Correct", "partial": "Right place, different issue",
                "false_alarm": "False alarm", "duplicate": "Duplicate of another flag"}


def _flag_review(sc: dict, charts: dict, traps: list[dict], res: dict) -> None:
    sid = sc["id"]
    by_id = {t["id"]: t for t in traps}
    st.subheader("Review")
    a, b, c = st.columns(3)
    a.metric("Issues found", f"{res['detected']} of {res['n_traps']}")
    b.metric("Partly right", res["partial"])
    c.metric("False alarms", res["false_alarms"])
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
            st.error(head + " Nothing misleading was planted here. Not every movement on a chart is a problem.")
    for t in res["missed"]:
        st.error(f"**Missed: {t['title']}** ({charts[t['charts'][0]]['title']}, weeks "
                 f"{t['weeks'][0]}–{t['weeks'][1]}). {ISSUES[t['issue']]}. {t['explanation']}")
    st.markdown("**Confidence check**")
    st.write(S.calibration_message(res["calibration"]))
    if st.button("Continue to the decision", type="primary", key=f"{sid}_go_dec"):
        go(sid, "decision")
        st.rerun()


# ------------------------------------------------------------------ stage: decision
def stage_decision(sc: dict) -> None:
    sid, stt = sc["id"], state(sc["id"])
    d = sc["decision"]
    done = stt["decision"] is not None
    st.write(d["question"])
    choice = st.radio("Your recommendation", list(DECISIONS), format_func=DECISIONS.get, index=None,
                      key=f"{sid}_dec", disabled=done)
    st.markdown("**Which observations support your recommendation?** Select all that apply.")
    evidence = shuffled(d["evidence"], sid + "_ev")
    chosen = [e["id"] for e in evidence
              if st.checkbox(e["text"], key=f"{sid}_ev_{e['id']}", disabled=done)]
    if not done:
        text = st.text_area("Your rationale, as you would say it in the launch review",
                            key=f"{sid}_rat", height=150,
                            placeholder="State your recommendation, the evidence for it, and what you would monitor next.")
        n = S.word_count(text)
        st.caption(f"{n} words (at least {MIN_WORDS}). Word count updates when you click outside the box.")

    if not done:
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
                log(sid, "decision", "decision_submitted", choice=choice, evidence=chosen,
                    words=n, rationale=text, **{k: v for k, v in stt["decision"].items()
                                               if k not in ("choice", "text", "decision_feedback")})
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
    # Shown as plain text, not the locked text box: a disabled text area came back empty
    # after submission in browser testing, hiding the learner's own words at the moment of comparison.
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
               "The same rubric is used to score the final transfer task.")
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
    a.metric("Metrics sorted correctly", f"{stt['sort']['n_correct']}/{stt['sort']['n_total']}")
    b.metric("Issues found", f"{fr['detected']}/{fr['n_traps']}",
             help="Partly right flags and false alarms are listed on the dashboard review.")
    cal = fr["calibration"]
    c.metric("Confidence vs. accuracy", S.calibration_label(cal),
             help=S.calibration_message(cal))
    d.metric("Decision", DECISIONS[dr["choice"]].split(":")[0],
             help=dr["decision_feedback"])
    st.write(f"Hints used: {len(stt['hints'])}. Self-assessment total: "
             f"{sum(stt['self_ratings'].values())} of 16.")
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
            rows.append([sc["title"], "In progress" if stt["stage"] != "brief" else "Not started", "", "", ""])
            continue
        fr, cal = stt["flag_result"], stt["flag_result"]["calibration"]
        rows.append([sc["title"], "Done", f"{stt['sort']['n_correct']}/{stt['sort']['n_total']}",
                     f"{fr['detected']}/{fr['n_traps']}", S.calibration_label(cal)])
    st.table(pd.DataFrame(rows, columns=["Scenario", "Status", "Metrics sorted", "Issues found",
                                         "Confidence vs. accuracy"]).set_index("Scenario"))
    st.download_button("Download activity log (CSV)", to_csv(), "metric_lab_log.csv", "text/csv",
                       key="dl_results")


def main() -> None:
    page = sidebar()
    if page == "Start here":
        start_page()
    elif page == "My results":
        results_page()
    else:
        scenario_page(next(s for s in C.scenarios() if s["title"] == page))


main()
