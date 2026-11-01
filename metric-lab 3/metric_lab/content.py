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


def md(text: str) -> str:
    """Escape dollar signs. Streamlit markdown treats text between two "$" as a math formula,
    so "$50 to $499.99" rendered garbled on the deployed app (found in deployment testing)."""
    return text.replace("$", "\\$") if isinstance(text, str) else text


# Machine-read values that must never be escaped: "yfmt" is a Plotly/d3 number format such as
# "$,.0f" (escaping it broke the dollar axes in Scenario 3, found in live testing).
_RAW_KEYS = {"yfmt", "id", "col", "num", "den", "kind", "issue", "role"}


def _escape(obj, path=()):
    """Recursively escape every display string, except Plotly series labels (Plotly is not markdown)."""
    if isinstance(obj, dict):
        return {k: (v if (path[-1:] == ("series",) and k == "label") or k in _RAW_KEYS
                    else _escape(v, path + (k,)))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_escape(v, path) for v in obj]
    return md(obj)


@lru_cache(maxsize=None)
def scenarios() -> list[dict]:
    items = [_escape(json.loads(p.read_text())) for p in (ROOT / "content").glob("scenario*.json")]
    return sorted(items, key=lambda s: s["order"])


def scenario(sid: str) -> dict:
    return next(s for s in scenarios() if s["id"] == sid)


@lru_cache(maxsize=None)
def data(sid: str) -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / f"{sid}_data.csv")


@lru_cache(maxsize=None)
def traps(sid: str) -> list[dict]:
    return _escape(json.loads((ROOT / "data" / f"{sid}_key.json").read_text())["traps"])


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
