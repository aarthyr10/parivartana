from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.theme import (
    empty_state,
    inject_global_styles,
    render_page_header,
    render_sidebar,
)
from src.utils.io import read_json
from src.utils.paths import OUTPUTS_DIR

st.set_page_config(page_title="Metrics - PARIVARTANA", layout="wide")
inject_global_styles()
render_sidebar("Metrics")


def _load_runs() -> list[dict]:
    if not OUTPUTS_DIR.exists():
        return []
    runs = []
    for path in sorted(OUTPUTS_DIR.glob("batch_*.json"), reverse=True):
        try:
            payload = read_json(path)
        except Exception:
            continue
        runs.append(
            {
                "file": path.name,
                "path": str(path),
                "dataset": payload.get("dataset", ""),
                "summary": payload.get("summary", {}),
                "records": payload.get("records", []),
                "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
            }
        )
    return runs


def main() -> None:
    render_page_header(eyebrow="METRICS", title="Metrics")

    runs = _load_runs()
    if not runs:
        empty_state(
            title="No runs",
            description="Save a batch run from the Batch Run page.",
            action_label="Batch Run",
            action_target="/Batch_Run",
        )
        return

    history = pd.DataFrame(
        [
            {
                "file": r["file"],
                "dataset": r["dataset"],
                "modified": r["modified"],
                "count": r["summary"].get("count", 0),
                "parse_success_rate": r["summary"].get("parse_success_rate", 0.0),
                "mean_complexity": r["summary"].get("mean_complexity", 0.0),
                "elapsed_seconds": r["summary"].get("elapsed_seconds", 0.0),
            }
            for r in runs
        ]
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Runs", len(history))
    m2.metric("Datasets", history["dataset"].nunique())
    m3.metric("Avg parse success", f"{history['parse_success_rate'].mean() * 100:.1f}%")
    m4.metric("Avg complexity", f"{history['mean_complexity'].mean():.2f}")

    st.markdown("<div class='pv-divider'></div>", unsafe_allow_html=True)

    st.markdown("**Runs**")
    st.dataframe(history, width="stretch", hide_index=True)

    if len(history) >= 2:
        st.markdown("**Trend**")
        trend = history.iloc[::-1].reset_index(drop=True)
        c1, c2 = st.columns(2)
        with c1:
            st.line_chart(trend, x="modified", y="parse_success_rate", height=240, width="stretch")
        with c2:
            st.line_chart(trend, x="modified", y="mean_complexity", height=240, width="stretch")

    st.markdown("<div class='pv-divider'></div>", unsafe_allow_html=True)
    st.markdown("**Detail**")
    selected = st.selectbox("Run", options=[r["file"] for r in runs])
    run = next(r for r in runs if r["file"] == selected)

    summary = run["summary"]
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Records", summary.get("count", 0))
    d2.metric("Parse success", f"{summary.get('parse_success_rate', 0.0) * 100:.1f}%")
    d3.metric("Mean complexity", f"{summary.get('mean_complexity', 0.0):.2f}")
    d4.metric("Elapsed", f"{summary.get('elapsed_seconds', 0.0):.1f} s")

    if summary.get("tier_distribution"):
        st.markdown("**Tier distribution**")
        tier_df = pd.DataFrame(
            list(summary["tier_distribution"].items()), columns=["tier", "count"]
        )
        st.bar_chart(tier_df, x="tier", y="count", height=220, width="stretch")

    if run["records"]:
        with st.expander("Records"):
            st.dataframe(pd.DataFrame(run["records"]), width="stretch", hide_index=True)


main()
