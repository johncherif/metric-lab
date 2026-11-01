"""Pure scoring functions for Metric Lab (no Streamlit imports, so they are unit-testable).

Design notes (each one is an edge case found while building):
  * A flag only matches a trap if MOST of the flag lies inside the trap's weeks
    (MIN_INSIDE_SHARE). Otherwise one flag covering weeks 1-12 would "find" every trap.
  * Each trap can be credited once. Extra flags on an already-found trap are
    labelled "duplicate" and are not counted as false alarms or as correct.
  * When a flag overlaps several traps on the same chart, it is matched to the trap
    with the same issue type first, then to the one it overlaps most.
  * Calibration is undefined with no flags, so it returns None rather than 0, and the
    feedback message refuses to judge calibration from a single flag.
"""
from __future__ import annotations

from dataclasses import dataclass, field

MIN_INSIDE_SHARE = 0.5   # at least half of a flag's weeks must fall inside the trap
SCORE_VALUE = {"correct": 1.0, "partial": 0.5, "false_alarm": 0.0, "duplicate": None}


# ---------------------------------------------------------------- Stage 1
def score_sorting(answers: dict[str, str], metrics: list[dict]) -> dict:
    """answers maps metric name -> chosen role. Unanswered metrics count as wrong."""
    results = []
    for m in metrics:
        chosen = answers.get(m["name"])
        results.append({"name": m["name"], "chosen": chosen, "correct_role": m["role"],
                        "correct": chosen == m["role"], "feedback": m["feedback"]})
    n_correct = sum(r["correct"] for r in results)
    return {"results": results, "n_correct": n_correct, "n_total": len(metrics),
            "score": n_correct / len(metrics) if metrics else 0.0}


# ---------------------------------------------------------------- Stage 2
@dataclass
class Flag:
    chart: str
    weeks: tuple[int, int]
    issue: str
    confidence: int  # 50-100
    meta: dict = field(default_factory=dict)

    def normalized(self) -> "Flag":
        a, b = sorted(int(w) for w in self.weeks)
        return Flag(self.chart, (a, b), self.issue, int(self.confidence), self.meta)


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Number of whole weeks shared by two inclusive week ranges."""
    return max(0, min(a[1], b[1]) - max(a[0], b[0]) + 1)


def match_flag(flag: Flag, traps: list[dict]) -> tuple[dict | None, int]:
    """Return (trap, overlap_weeks) for the best qualifying trap, or (None, 0)."""
    f = flag.normalized()
    width = f.weeks[1] - f.weeks[0] + 1
    candidates = []
    for t in traps:
        if f.chart not in t["charts"]:
            continue
        ov = _overlap(f.weeks, tuple(t["weeks"]))
        if ov and ov / width >= MIN_INSIDE_SHARE:
            candidates.append((t["issue"] == f.issue, ov, t))
    if not candidates:
        return None, 0
    same_type, ov, trap = max(candidates, key=lambda c: (c[0], c[1]))
    return trap, ov


def score_flags(flags: list[Flag], traps: list[dict]) -> dict:
    """Score every flag and list the traps that were missed."""
    found: dict[str, str] = {}          # trap id -> best outcome so far
    scored = []
    for fl in flags:
        trap, _ = match_flag(fl, traps)
        if trap is None:
            outcome, trap_id = "false_alarm", None
        else:
            trap_id = trap["id"]
            outcome = "correct" if trap["issue"] == fl.issue else "partial"
            prev = found.get(trap_id)
            if prev == "correct" or (prev == "partial" and outcome == "partial"):
                outcome = "duplicate"
            else:
                found[trap_id] = outcome
        scored.append({"flag": fl, "outcome": outcome, "trap_id": trap_id,
                       "value": SCORE_VALUE[outcome]})
    # A later correct flag upgrades an earlier partial one; mark the earlier partial as duplicate.
    for tid, best in found.items():
        if best == "correct":
            for s in scored:
                if s["trap_id"] == tid and s["outcome"] == "partial":
                    s["outcome"], s["value"] = "duplicate", None
    missed = [t for t in traps if t["id"] not in found]
    detected = sum(1 for t in traps if found.get(t["id"]) == "correct")
    partial = sum(1 for t in traps if found.get(t["id"]) == "partial")
    false_alarms = sum(1 for s in scored if s["outcome"] == "false_alarm")
    return {"scored": scored, "missed": missed, "n_traps": len(traps), "detected": detected,
            "partial": partial, "false_alarms": false_alarms,
            "score": (detected + 0.5 * partial) / len(traps) if traps else 0.0}


def calibration(scored: list[dict]) -> dict | None:
    """Compare stated confidence with outcomes. Duplicates are excluded.

    gap  = mean |confidence - outcome value|   (0 is perfect calibration)
    bias = mean confidence - mean outcome      (> 0 means overconfident)
    """
    rows = [s for s in scored if s["value"] is not None]
    if not rows:
        return None
    conf = [s["flag"].confidence / 100 for s in rows]
    val = [s["value"] for s in rows]
    gap = sum(abs(c - v) for c, v in zip(conf, val)) / len(rows)
    bias = sum(conf) / len(conf) - sum(val) / len(val)
    overconfident = [s for s in rows if s["flag"].confidence >= 80 and s["value"] == 0.0]
    return {"gap": gap, "bias": bias, "n": len(rows), "overconfident_misses": len(overconfident)}


def calibration_label(cal: dict | None) -> str:
    """One-word summary that always agrees with calibration_message (same thresholds).

    The raw gap is not shown on its own: with confidence limited to 50-100% and outcomes of 0 or 1,
    even a well-calibrated learner has a large gap, which contradicted the message in live testing."""
    if cal is None:
        return "No flags"
    if cal["n"] < 2:
        return "Too few flags"
    if cal["bias"] > 0.15:
        return "Overconfident"
    if cal["bias"] < -0.15:
        return "Underconfident"
    return "Well matched"


def calibration_message(cal: dict | None) -> str:
    if cal is None:
        return "You did not submit any flags, so there is nothing to calibrate yet."
    if cal["overconfident_misses"]:
        k = cal["overconfident_misses"]
        lead = f"You were at least 80% sure on {k} flag{'s' if k > 1 else ''} that turned out to be false alarm{'s' if k > 1 else ''}. "
    else:
        lead = ""
    if cal["n"] < 2:
        return lead + ("With only one scored flag, there is not enough evidence to judge how well your "
                       "confidence matches your accuracy.")
    if cal["bias"] > 0.15:
        tail = "Overall your confidence ran well ahead of your accuracy. Before flagging, try to name the specific evidence on the chart."
    elif cal["bias"] < -0.15:
        tail = "You were more accurate than you expected. Trust your reading of the charts a little more."
    else:
        tail = "Your confidence was reasonably well matched to your accuracy."
    return lead + tail


# ---------------------------------------------------------------- Stage 3
def score_decision(choice: str, evidence_ids: list[str], decision_cfg: dict) -> dict:
    opt = decision_cfg["options"].get(choice)
    required = set(decision_cfg["required_evidence"])
    relevant = {e["id"] for e in decision_cfg["evidence"] if e["relevant"]}
    chosen = set(evidence_ids)
    return {
        "decision_score": opt["score"] if opt else 0.0,
        "decision_feedback": opt["feedback"] if opt else "No decision selected.",
        "required_cited": len(required & chosen),
        "required_total": len(required),
        "irrelevant_cited": sorted(chosen - relevant),
        "evidence_score": len(required & chosen) / len(required) if required else 1.0,
    }


def word_count(text: str) -> int:
    return len([w for w in (text or "").split() if any(ch.isalnum() for ch in w)])
