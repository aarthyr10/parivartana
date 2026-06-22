
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.theme import (
    badge,
    empty_state,
    inject_global_styles,
    render_page_header,
    render_sidebar,
)
from src.utils.paths import RUNS_DIR

st.set_page_config(page_title="Past Runs - PARIVARTANA", layout="wide")
inject_global_styles()
render_sidebar("Past Runs")


_VERDICT_KIND = {
    "PASS": "success",
    "STRUCTURAL_PASS": "success",
    "FAIL": "danger",
    "INCONCLUSIVE": "warning",
}


def _verdict_kind(verdict: str) -> str:
    return _VERDICT_KIND.get(verdict, "neutral")


@dataclass
class RunDir:
    path: Path
    name: str
    mtime: float

    @property
    def has_summary(self) -> bool:
        return (self.path / "summary.md").exists()

    @property
    def trace_count(self) -> int:
                                                                      
                                                           
        excluded = {"patterns.json"}
        return sum(
            1
            for f in self.path.glob("*.json")
            if f.name not in excluded
        )


def _list_runs() -> list[RunDir]:
    if not RUNS_DIR.exists():
        return []
    out: list[RunDir] = []
    for entry in RUNS_DIR.iterdir():
        if not entry.is_dir():
            continue
        try:
            mtime = entry.stat().st_mtime
        except OSError:
            mtime = 0.0
        out.append(RunDir(path=entry, name=entry.name, mtime=mtime))
    out.sort(key=lambda r: r.mtime, reverse=True)
    return out


@st.cache_data(show_spinner=False)
def _load_run_traces(run_dir: str) -> list[dict]:
    out: list[dict] = []
    run_path = Path(run_dir)
    for f in run_path.glob("*.json"):
        if f.name == "patterns.json":
            continue
        try:
            out.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
                                                                      
    out.sort(key=lambda d: d.get("timestamp") or 0, reverse=True)
    return out


@st.cache_data(show_spinner=False)
def _load_patterns(run_dir: str) -> dict:
    p = Path(run_dir) / "patterns.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


@st.cache_data(show_spinner=False)
def _load_summary_md(run_dir: str) -> str:
    p = Path(run_dir) / "summary.md"
    return p.read_text() if p.exists() else ""


@st.cache_data(show_spinner=False)
def _load_run_log(run_dir: str) -> str:
    p = Path(run_dir) / "run.log"
    return p.read_text() if p.exists() else ""


def _verdict_counts(traces: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for t in traces:
        v = t.get("verdict", "UNKNOWN")
        counts[v] = counts.get(v, 0) + 1
    return counts


def _headline_pass_rate(counts: dict[str, int]) -> tuple[int, int, float]:
    pass_n = counts.get("PASS", 0) + counts.get("STRUCTURAL_PASS", 0)
    total = sum(counts.values())
    pct = (100.0 * pass_n / total) if total else 0.0
    return pass_n, total, pct


def _render_run_list(runs: list[RunDir]) -> None:
    render_page_header("Workspace", "Past Runs", "Browse outputs from CLI batch runs.")

    if not runs:
        empty_state(
            "No past runs found",
            f"Nothing under `{RUNS_DIR}` yet. Run `python scripts/batch_run.py ...` "
            "or use the Batch Run page first.",
        )
        return

                                        
    rows = []
    for r in runs:
        traces = _load_run_traces(str(r.path))
        counts = _verdict_counts(traces)
        pass_n, total, pct = _headline_pass_rate(counts)
        rows.append(
            {
                "Run": r.name,
                "Traces": r.trace_count,
                "PASS%": f"{pct:.1f}%",
                "PASS": counts.get("PASS", 0),
                "STRUCTURAL_PASS": counts.get("STRUCTURAL_PASS", 0),
                "FAIL": counts.get("FAIL", 0),
                "INCONCLUSIVE": counts.get("INCONCLUSIVE", 0),
                "Modified": pd.Timestamp(r.mtime, unit="s").strftime("%Y-%m-%d %H:%M"),
                "_path": str(r.path),
                "_name": r.name,
            }
        )
    df = pd.DataFrame(rows)

                                       
    c1, c2, c3 = st.columns(3)
    c1.metric("Runs", len(runs))
    c2.metric("Total traces", int(df["Traces"].sum()))
    if not df.empty and df["Traces"].sum() > 0:
        avg_pass = (
            100.0
            * (df["PASS"].sum() + df["STRUCTURAL_PASS"].sum())
            / df["Traces"].sum()
        )
        c3.metric("Avg headline PASS%", f"{avg_pass:.1f}%")
    else:
        c3.metric("Avg headline PASS%", "—")

    st.divider()
    st.subheader("Runs")
                                                                     
    display_df = df.drop(columns=["_path", "_name"])
    st.dataframe(display_df, width="stretch", hide_index=True)

                                                                     
    st.markdown("**Open a run for details:**")
    selected = st.selectbox(
        "Run",
        options=df["_name"].tolist(),
        label_visibility="collapsed",
    )
    if st.button("View details →", type="primary"):
        st.session_state["pv_open_run"] = selected
        st.rerun()


def _render_run_detail(run_name: str) -> None:
    run_path = RUNS_DIR / run_name
    if not run_path.exists():
        st.error(f"Run folder not found: {run_path}")
        return

    render_page_header("Workspace", run_name, f"Browsing `artifacts/runs/{run_name}/`")
    if st.button("← Back to all runs"):
        st.session_state.pop("pv_open_run", None)
        st.session_state.pop("pv_open_program", None)
        st.rerun()

    traces = _load_run_traces(str(run_path))
    counts = _verdict_counts(traces)
    pass_n, total, pct = _headline_pass_rate(counts)

                       
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Headline PASS%", f"{pct:.1f}%", f"{pass_n}/{total}")
    m2.metric("PASS", counts.get("PASS", 0))
    m3.metric("STRUCTURAL_PASS", counts.get("STRUCTURAL_PASS", 0))
    m4.metric("FAIL", counts.get("FAIL", 0))
    m5.metric("INCONCLUSIVE", counts.get("INCONCLUSIVE", 0))

                                                 
    tab_summary, tab_programs, tab_patterns, tab_log = st.tabs(
        ["Summary", "Programs", "Failure patterns", "Run log"]
    )

    with tab_summary:
        summary = _load_summary_md(str(run_path))
        if summary:
            st.markdown(summary)
        else:
            st.info("No `summary.md` in this run folder.")

    with tab_programs:
        if not traces:
            st.warning("No per-program traces in this run folder.")
        else:
            _render_program_table(traces, run_name)

    with tab_patterns:
        patterns = _load_patterns(str(run_path))
        if not patterns:
            st.info("No `patterns.json` (or patterns dict is empty).")
        else:
            for bucket, items in patterns.items():
                st.markdown(f"### `{bucket}`")
                pdf = pd.DataFrame(items)
                if not pdf.empty:
                    st.dataframe(pdf, width="stretch", hide_index=True)

    with tab_log:
        log = _load_run_log(str(run_path))
        if log:
            st.code(log, language="text")
        else:
            st.info("No `run.log` in this run folder.")


def _render_program_table(traces: list[dict], run_name: str) -> None:
    rows = []
    for t in traces:
        rows.append(
            {
                "Program": t.get("program_id", "?"),
                "Tier": t.get("complexity_tier", "?"),
                "Verdict": t.get("verdict", "?"),
                "Stage1 ok": "✓" if t.get("stage1_ok") else "✗",
                "Stage2": t.get("stage2_source", "—"),
                "Stage3 ran": "✓" if t.get("stage3_ran") else "—",
                "Summary": (t.get("verdict_summary") or "")[:80],
                "_program_id": t.get("program_id"),
                "_record_id": t.get("record_id"),
                "_timestamp": t.get("timestamp"),
            }
        )
    df = pd.DataFrame(rows)

                     
    fc1, fc2 = st.columns([2, 1])
    with fc1:
        verdict_filter = st.multiselect(
            "Filter by verdict",
            options=sorted({r["Verdict"] for r in rows}),
            default=[],
            placeholder="(showing all)",
        )
    with fc2:
        search = st.text_input("Search program ID", placeholder="e.g. SQ143A")

    filtered = df.copy()
    if verdict_filter:
        filtered = filtered[filtered["Verdict"].isin(verdict_filter)]
    if search:
        filtered = filtered[
            filtered["Program"].str.contains(search, case=False, na=False)
        ]

    st.caption(f"Showing {len(filtered)} of {len(df)} program(s).")
    st.dataframe(
        filtered.drop(columns=["_program_id", "_record_id", "_timestamp"]),
        width="stretch",
        hide_index=True,
    )

    if filtered.empty:
        return

                                     
    program_options = filtered["Program"].tolist()
    chosen = st.selectbox(
        "Open program",
        options=program_options,
        index=0,
    )
    if st.button("View program →", type="primary", key="open_program"):
        st.session_state["pv_open_program"] = chosen
        st.rerun()


def _render_program_detail(run_name: str, program_id: str) -> None:
    run_path = RUNS_DIR / run_name
    traces = _load_run_traces(str(run_path))
    trace = next((t for t in traces if t.get("program_id") == program_id), None)
    if trace is None:
        st.error(f"Program `{program_id}` not found in run `{run_name}`.")
        if st.button("← Back to programs"):
            st.session_state.pop("pv_open_program", None)
            st.rerun()
        return

    render_page_header(run_name, program_id, trace.get("verdict_summary", "")[:140])
    back_cols = st.columns([1, 1, 6])
    with back_cols[0]:
        if st.button("← Run summary"):
            st.session_state.pop("pv_open_program", None)
            st.rerun()
    with back_cols[1]:
        if st.button("← All runs"):
            st.session_state.pop("pv_open_program", None)
            st.session_state.pop("pv_open_run", None)
            st.rerun()

                     
    verdict = trace.get("verdict", "INCONCLUSIVE")
    kind = _verdict_kind(verdict)
    h1, h2, h3, h4 = st.columns(4)
    h1.markdown(badge(verdict, kind), unsafe_allow_html=True)
    h2.metric("Tier", trace.get("complexity_tier", "?"))
    h3.metric("Stage 2 source", trace.get("stage2_source", "—"))
    h4.metric("Stage 3 ran", "yes" if trace.get("stage3_ran") else "no")

                           
    st.subheader("Verifier checks")
    check_rows = []
    for c in trace.get("verdict_checks", []):
        check_rows.append(
            {
                "Check": c.get("name", "?"),
                "Ran": "yes" if c.get("ran") else "no",
                "Passed": (
                    "✓"
                    if c.get("passed") is True
                    else ("✗" if c.get("passed") is False else "—")
                ),
                "Score": c.get("score"),
                "Detail / reason": (c.get("detail") or c.get("skipped_reason") or "")[:200],
            }
        )
    if check_rows:
        st.dataframe(pd.DataFrame(check_rows), width="stretch", hide_index=True)
    else:
        st.info("No verifier checks recorded.")

                          
    tabs = st.tabs(
        ["COBOL source", "Stage 2 Python", "Stage 3 refined Python", "Full trace JSON"]
    )
    with tabs[0]:
        st.code(trace.get("cobol_source", "") or "(empty)", language="cobol")
    with tabs[1]:
        st.code(trace.get("stage2_final_code", "") or "(empty)", language="python")
    with tabs[2]:
        s3 = trace.get("stage3_refined_code") or ""
        if s3:
            st.code(s3, language="python")
        else:
            st.info("Stage 3 did not produce refined code for this program.")
    with tabs[3]:
                                                                         
        slim = {k: v for k, v in trace.items() if k not in {"stage1_ast", "cobol_source"}}
        st.json(slim)


runs = _list_runs()
open_run = st.session_state.get("pv_open_run")
open_program = st.session_state.get("pv_open_program")

if open_run and open_program:
    _render_program_detail(open_run, open_program)
elif open_run:
    _render_run_detail(open_run)
else:
    _render_run_list(runs)
