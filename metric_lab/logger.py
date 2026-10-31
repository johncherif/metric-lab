"""In-session event log, exportable as CSV. No personal data is collected."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

import streamlit as st

FIELDS = ["timestamp", "scenario", "stage", "event", "detail"]


def log(scenario: str, stage: str, event: str, **detail) -> None:
    st.session_state.setdefault("events", []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scenario": scenario, "stage": stage, "event": event,
        "detail": json.dumps(detail, default=str),
    })


def events() -> list[dict]:
    return st.session_state.get("events", [])


def to_csv() -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(events())
    return buf.getvalue().encode("utf-8")
