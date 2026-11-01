"""The generator must actually plant the traps its answer key describes."""
import pandas as pd
import pytest

from generator.generate import SCENARIOS, scenario1


def _rate(df, num, den):
    g = df.groupby("week")[[num, den]].sum()
    return g[num] / g[den]


def test_generator_is_deterministic():
    a, _ = scenario1()
    b, _ = scenario1()
    pd.testing.assert_frame_equal(a, b)


def test_scenario1_blended_rate_drops_but_original_base_does_not():
    data, _ = scenario1()
    blended = _rate(data, "plans", "shown")
    orig = _rate(data[data.segment == "Originally eligible"], "plans", "shown")
    assert blended.loc[5:12].mean() < 0.75 * blended.loc[1:4].mean()      # headline drop
    assert orig.loc[5:12].mean() >= orig.loc[1:4].mean()                   # original base healthy


def test_scenario1_optout_guardrail_worsens():
    data, _ = scenario1()
    opt = _rate(data, "opt_outs", "shown")
    assert opt.loc[5:12].mean() > 2 * opt.loc[1:4].mean()


def test_product_columns_sum_to_total():
    for fn in SCENARIOS.values():
        data, _ = fn()
        prod_cols = [c for c in data.columns if c.startswith("plans_")]
        if prod_cols:
            assert (data[prod_cols].sum(axis=1) == data["plans"]).all()


from generator.generate import scenario2, scenario3


def test_scenario2_simpsons_paradox():
    data, _ = scenario2()
    blended = _rate(data, "repeat_users", "cohort_users")
    assert blended.loc[10:12].mean() > blended.loc[1:3].mean()             # total rises
    for seg in data.segment.unique():
        r = _rate(data[data.segment == seg], "repeat_users", "cohort_users")
        assert r.loc[10:12].mean() < r.loc[1:3].mean()                      # every segment falls


def test_scenario2_novelty_and_threshold():
    data, _ = scenario2()
    ppu = _rate(data, "plans", "active_users")
    assert ppu.loc[1] > 1.5 * ppu.loc[6:12].mean()
    assert abs(ppu.loc[6:12].max() - ppu.loc[6:12].min()) < 0.05            # steady state
    g = data.groupby("week")[["band_450_499", "band_500_549"]].sum()
    assert (g.band_450_499 > 2.5 * g.band_500_549).all()


def test_scenario3_lagging_risk_and_cannibalization():
    data, _ = scenario3()
    np_ = data[data.segment == "Near-prime (below 720)"].set_index("week")
    fpd = np_.fpd_flexplan / np_.due_flexplan.where(np_.due_flexplan > 0)
    assert fpd.loc[1:4].isna().all()                                         # nothing due yet
    assert fpd.loc[11:12].mean() > 2.5 * fpd.loc[5:6].mean()
    assert data.chargeoffs.sum() == 0
    g = data.groupby("week").sum(numeric_only=True)
    card = g.card_interest_flexplan_users / g.flexplan_customers
    assert card.loc[12] < 0.5 * card.loc[1]
