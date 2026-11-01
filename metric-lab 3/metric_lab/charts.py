"""Plotly figures for the dashboard, with optional shaded regions for traps."""
from __future__ import annotations

import plotly.graph_objects as go

# Colorblind-safe palette (Okabe-Ito subset)
SERIES_COLORS = ["#0072B2", "#E69F00", "#009E73", "#CC79A7"]
SHADE = {
    "guide": ("rgba(230,159,0,0.18)", "Analyst: look here"),
    "found": ("rgba(0,158,115,0.16)", "You found this"),
    "missed": ("rgba(213,94,0,0.18)", "Missed"),
}


def figure(frame, chart: dict, shades: list[tuple[list[int], str]] = ()) -> go.Figure:
    fig = go.Figure()
    labels = [c for c in frame.columns if c != "week"]
    for i, label in enumerate(labels):
        fig.add_trace(go.Scatter(
            x=frame["week"], y=frame[label], name=label, mode="lines+markers",
            line=dict(color=SERIES_COLORS[i % len(SERIES_COLORS)], width=2.5),
            marker=dict(size=7),
            hovertemplate=f"Week %{{x}}<br>{label}: %{{y:{chart['yfmt']}}}<extra></extra>",
            connectgaps=False,
        ))
    for weeks, kind in shades:
        color, text = SHADE[kind]
        fig.add_vrect(x0=weeks[0] - 0.5, x1=weeks[1] + 0.5, fillcolor=color, line_width=0,
                      annotation_text=text, annotation_position="top left",
                      annotation_font_size=11, annotation_font_color="#B36B00", layer="below")
    fig.update_layout(
        # Title is drawn by Streamlit above the chart so long titles wrap on narrow screens.
        height=300, margin=dict(l=10, r=10, t=30, b=10),
        dragmode="select", hovermode="x unified",
        showlegend=len(labels) > 1,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )   # no hard-coded background: Streamlit's theme styles the chart in light and dark mode
    fig.update_xaxes(title_text="Week since launch", dtick=1, range=[0.5, 12.5], fixedrange=True)
    fig.update_yaxes(tickformat=chart["yfmt"], rangemode="tozero", fixedrange=True)
    if chart.get("ymax"):   # shared scale, e.g. so a 0% charge-off line sits beside default rates honestly
        fig.update_yaxes(range=[0, chart["ymax"]])
    return fig


def weeks_from_selection(selection) -> tuple[int, int] | None:
    """Turn a Streamlit Plotly selection into an inclusive week range.

    Box edges are rounded to the nearest week, so a box that starts just past a marker
    still includes that week (found in browser testing: a drag starting at x=5.1 missed
    week 5 when only the selected points were used). Clicked points are the fallback."""
    if not selection:
        return None
    boxes = selection.get("box") or []
    if boxes and boxes[0].get("x"):
        x0, x1 = sorted(boxes[0]["x"][:2])
        a, b = max(1, int(round(x0))), min(12, int(round(x1)))
        if a <= b:
            return a, b
    pts = selection.get("points") or []
    xs = [p.get("x") for p in pts if p.get("x") is not None]
    if xs:
        return int(round(min(xs))), int(round(max(xs)))
    return None
