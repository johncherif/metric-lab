"""Loading scenario content, generated data, and answer keys; aggregating chart data."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ALL_SEGMENTS = "All customers"


@lru_cache(maxsize=None)
def common() -> dict:
    return json.loads((ROOT / "content" / "common.json").read_text())


@lru_cache(maxsize=None)
def scenarios() -> list[dict]:
    items = [json.loads(p.read_text()) for p in (ROOT / "content").glob("scenario*.json")]
    return sorted(items, key=lambda s: s["order"])


def scenario(sid: str) -> dict:
    return next(s for s in scenarios() if s["id"] == sid)


@lru_cache(maxsize=None)
def data(sid: str) -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / f"{sid}_data.csv")


@lru_cache(maxsize=None)
def traps(sid: str) -> list[dict]:
    return json.loads((ROOT / "data" / f"{sid}_key.json").read_text())["traps"]


def chart_frame(sid: str, chart: dict, segment: str = ALL_SEGMENTS) -> pd.DataFrame:
    """Weekly values for one chart. Rates are recomputed from summed counts, so a rate
    for 'All customers' is a properly weighted blend, never an average of averages."""
    df = data(sid)
    if segment != ALL_SEGMENTS:
        df = df[df["segment"] == segment]
    weeks = pd.DataFrame({"week": range(1, 13)})
    out = weeks.copy()
    for s in chart["series"]:
        if chart["kind"] == "count":
            g = df.groupby("week")[s["col"]].sum()
            out[s["label"]] = weeks["week"].map(g).fillna(0)
        else:  # rate
            g = df.groupby("week")[[s["num"], s["den"]]].sum()
            rate = g[s["num"]] / g[s["den"]].where(g[s["den"]] > 0)   # no division by zero
            out[s["label"]] = weeks["week"].map(rate)                 # NaN where no one was shown
    return out
