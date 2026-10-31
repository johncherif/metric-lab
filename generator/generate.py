"""Seeded synthetic-data generator for Metric Lab.

Each scenario function returns (data, traps):
  * data  - a DataFrame with one row per week x segment, holding raw COUNTS only
            (product breakdowns are separate count columns such as plans_flex4) (rates are always recomputed from counts in
            the app, so aggregating across segments never averages averages).
  * traps - the answer key: every analytical trap planted in that data, with the
            chart(s) and week range where it can be seen.

Writing data and answer key from the same function guarantees they never drift
apart. Run:  python -m generator.generate
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
WEEKS = np.arange(1, 13)
PRODUCTS = ["Flex 4", "Flex 4 Plus", "Flex Plan"]


def _slug(name: str) -> str:
    return name.lower().replace(" ", "")


def _binom(rng, n, p):
    return int(rng.binomial(max(int(n), 0), min(max(p, 0.0), 1.0)))


# --------------------------------------------------------------------------
# Scenario 1 - Adoption: eligibility expansion changes the denominator
# --------------------------------------------------------------------------
def scenario1(seed: int = 6460):
    rng = np.random.default_rng(seed)
    expansion_week = 5
    rows = []
    segments = {
        # name: (first week shown, weekly reach, creation rate, opt-out rate, product mix)
        "Originally eligible": (1, 40_000, 0.045, 0.006, [0.60, 0.15, 0.25]),
        "Newly eligible": (expansion_week, 52_000, 0.014, 0.022, [0.76, 0.12, 0.12]),
    }
    for seg, (start, reach, rate, optout, mix) in segments.items():
        for w in WEEKS:
            shown = int(rng.normal(reach, reach * 0.03)) if w >= start else 0
            # small organic improvement for the original base: the feature is healthy
            r = rate * (1 + 0.012 * (w - 1)) if seg == "Originally eligible" else rate
            plans = _binom(rng, shown, r)
            opt_outs = _binom(rng, shown, optout)
            split = rng.multinomial(plans, mix) if plans else [0, 0, 0]
            row = dict(week=int(w), segment=seg, shown=int(shown), plans=int(plans), opt_outs=int(opt_outs))
            for p, prod in enumerate(PRODUCTS):
                row[f"plans_{_slug(prod)}"] = int(split[p])
            rows.append(row)
    data = pd.DataFrame(rows)
    traps = [
        dict(id="s1_base", charts=["creation_rate", "impressions", "plans_by_product"], weeks=[expansion_week, 12],
             issue="base_changed",
             title="The plan creation rate fell because the base changed",
             explanation=("Eligibility was expanded in week 5. Roughly 52,000 newly eligible customers a week "
                          "started seeing the offer, and they convert at about 1.4%, versus about 4.5% for the "
                          "original base. The blended rate fell even though the original base kept improving. "
                          "Filter the dashboard to 'Originally eligible' to see it.")),
        dict(id="s1_optout", charts=["optout_rate"], weeks=[expansion_week, 12], issue="guardrail",
             title="The offer opt-out rate (a guardrail) more than doubled",
             explanation=("Newly eligible customers opt out of the offer at about 2.2%, versus 0.6% for the "
                          "original base. A rising opt-out rate signals the offer is reaching people who do not "
                          "want it, which can harm the customer relationship even while plan counts grow.")),
    ]
    return data, traps


# --------------------------------------------------------------------------
# Scenario 2 - Engagement: Simpson's paradox, novelty effect, fee-threshold bunching
# --------------------------------------------------------------------------
def scenario2(seed: int = 6461):
    rng = np.random.default_rng(seed)
    rows = []
    # Mix shifts toward existing cardholders, who repeat more. Within each segment the
    # repeat rate DECLINES, but the blended rate RISES (Simpson's paradox).
    share_existing = np.linspace(0.30, 0.75, 12)
    total_cohort = 9_000
    seg_cfg = {
        "Existing cardholders": dict(repeat=np.linspace(0.40, 0.33, 12), autopay=np.linspace(0.46, 0.58, 12)),
        "New to Harborline credit": dict(repeat=np.linspace(0.19, 0.14, 12), autopay=np.linspace(0.30, 0.41, 12)),
    }
    # Novelty: plans per active user starts high and settles by week 5.
    novelty = np.array([1.95, 1.62, 1.38, 1.22] + [1.15] * 8)
    for i, w in enumerate(WEEKS):
        for seg, cfg in seg_cfg.items():
            share = share_existing[i] if seg == "Existing cardholders" else 1 - share_existing[i]
            cohort = int(rng.normal(total_cohort * share, 120))
            repeaters = _binom(rng, cohort, cfg["repeat"][i])
            active = int(rng.normal(14_000 * share * (1 + 0.04 * i), 150))
            plans = int(round(active * novelty[i] * rng.normal(1, 0.015)))
            autopay = _binom(rng, plans, cfg["autopay"][i])
            # Purchases just below vs just above the $500 fee threshold. Without a behavioral
            # response these bands would be roughly equal; customers avoid the $25 fee.
            below = int(rng.poisson(plans * 0.090))
            above = int(rng.poisson(plans * 0.028))
            rows.append(dict(week=int(w), segment=seg, cohort_users=cohort, repeat_users=repeaters,
                             active_users=active, plans=plans, autopay_plans=autopay,
                             band_450_499=below, band_500_549=above))
    data = pd.DataFrame(rows)
    traps = [
        dict(id="s2_simpson", charts=["repeat_rate"], weeks=[1, 12], issue="segment_reversal",
             title="Repeat use is falling in every segment, even though the total is rising",
             explanation=("The blended repeat-plan rate rises from about 25% to about 29%, but filter by segment: "
                          "existing cardholders fall from about 40% to 33%, and new-to-credit customers from about 19% "
                          "to 14%. The total rises only because the mix shifted toward existing cardholders, who "
                          "repeat more. Engagement is getting worse, not better.")),
        dict(id="s2_novelty", charts=["plans_per_user"], weeks=[1, 4], issue="novelty",
             title="Early plans per user were a launch spike",
             explanation=("Plans per active user started near 2.0 in week 1 and settled at about 1.15 by week 5. "
                          "The launch weeks reflect curiosity and promotion. Judge engagement on the steady-state "
                          "weeks, not on a comparison with week 1.")),
        dict(id="s2_threshold", charts=["fee_threshold"], weeks=[1, 12], issue="threshold",
             title="Purchases bunch just below the $500 fee threshold",
             explanation=("About three times as many purchases fall between $450 and $499.99 as between $500 and "
                          "$549.99. Purchase sizes do not naturally drop off a cliff at $500; customers are keeping "
                          "purchases under the threshold to avoid the $25 Flex 4 Plus fee. The product rule is "
                          "shaping behavior, which matters for any fee or pricing decision.")),
    ]
    return data, traps


# --------------------------------------------------------------------------
# Scenario 3 - Value: lagging credit risk and cannibalization
# --------------------------------------------------------------------------
def scenario3(seed: int = 6462):
    rng = np.random.default_rng(seed)
    rows = []
    avg_ticket = {"Flex 4": 220, "Flex 4 Plus": 780, "Flex Plan": 1_450}
    seg_cfg = {
        # weekly new plans by product, growth per week, first-payment-default rate by product per week
        "Prime (score 720+)": dict(
            plans={"Flex 4": 5_200, "Flex 4 Plus": 900, "Flex Plan": 1_100}, growth=0.05,
            fpd={"Flex 4": np.full(12, 0.008), "Flex 4 Plus": np.full(12, 0.010),
                 "Flex Plan": np.full(12, 0.011)}),
        "Near-prime (below 720)": dict(
            plans={"Flex 4": 3_100, "Flex 4 Plus": 500, "Flex Plan": 900}, growth=0.09,
            fpd={"Flex 4": np.full(12, 0.016), "Flex 4 Plus": np.full(12, 0.021),
                 # rising early-warning signal for longer-term plans in near-prime
                 "Flex Plan": np.array([0.018] * 6 + [0.024, 0.031, 0.037, 0.043, 0.049, 0.054])}),
    }
    first_due_lag = 4   # first installment is due about 4 weeks after origination
    plans_hist = {seg: {p: [] for p in PRODUCTS} for seg in seg_cfg}
    for i, w in enumerate(WEEKS):
        for seg, cfg in seg_cfg.items():
            row = dict(week=int(w), segment=seg)
            for prod in PRODUCTS:
                n = int(rng.poisson(cfg["plans"][prod] * (1 + cfg["growth"]) ** i))
                plans_hist[seg][prod].append(n)
                s = _slug(prod)
                row[f"plans_{s}"] = n
                row[f"volume_{s}"] = int(n * avg_ticket[prod] * rng.normal(1, 0.02))
                due = plans_hist[seg][prod][i - first_due_lag] if i >= first_due_lag else 0
                row[f"due_{s}"] = due
                row[f"fpd_{s}"] = _binom(rng, due, cfg["fpd"][prod][i]) if due else 0
            row["plans"] = sum(row[f"plans_{_slug(p)}"] for p in PRODUCTS)
            row["due_all"] = sum(row[f"due_{_slug(p)}"] for p in PRODUCTS)
            row["chargeoffs"] = 0          # charge-off happens ~120+ days past due: impossible yet
            # Cannibalization: Flex Plan users move card revolving balances (about 24% APR) into Flex Plan
            # (15.99% APR). Card interest from these customers falls as Flex Plan interest rises.
            cum_flexplan = sum(plans_hist[seg]["Flex Plan"])
            # Stored as totals plus a customer count, so the app shows PER-CUSTOMER rates; a raw total
            # would rise with the growing customer base and hide the shift (found while building).
            row["flexplan_customers"] = cum_flexplan
            row["card_interest_flexplan_users"] = int(cum_flexplan * 21.0 * max(0.45, 1 - 0.055 * i) * rng.normal(1, 0.01))
            row["flexplan_interest"] = int(cum_flexplan * 14.0 * rng.normal(1, 0.01))
            rows.append(row)
    data = pd.DataFrame(rows)
    traps = [
        dict(id="s3_lagging", charts=["fpd_rate", "chargeoff_rate"], weeks=[7, 12], issue="lagging",
             title="Early defaults are rising in near-prime Flex Plan, while charge-offs still read zero",
             explanation=("Charge-offs cannot appear until about 120 days past due, so a zero charge-off rate 12 weeks "
                          "after launch says nothing about credit quality. The early-warning signal is the "
                          "first-payment default rate: for near-prime Flex Plan customers it rose from about 1.8% to "
                          "over 6% by week 12. Filter to 'Near-prime (below 720)' to see it clearly.")),
        dict(id="s3_cannibal", charts=["cannibalization"], weeks=[4, 12], issue="cannibalization",
             title="Flex Plan growth is partly moved from card balances",
             explanation=("Weekly card interest per Flex Plan customer fell from about $21 to under $10, while Flex "
                          "Plan interest per customer held near $14. Customers are moving balances from a roughly 24% card APR to a "
                          "15.99% Flex Plan. Part of the 'new' volume is existing borrowing at a lower rate, so net "
                          "value is lower than gross volume suggests.")),
    ]
    return data, traps


SCENARIOS = {"scenario1": scenario1, "scenario2": scenario2, "scenario3": scenario3}


def write_all() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    for name, fn in SCENARIOS.items():
        data, traps = fn()
        data.to_csv(DATA_DIR / f"{name}_data.csv", index=False)
        (DATA_DIR / f"{name}_key.json").write_text(json.dumps({"traps": traps}, indent=2))
        print(f"wrote {name}: {len(data)} rows, {len(traps)} traps")


if __name__ == "__main__":
    write_all()
