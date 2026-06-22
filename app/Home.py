from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.theme import (
    StageStatus,
    badge,
    inject_global_styles,
    render_page_header,
    render_sidebar,
    render_stage_status,
)
from src.data.registry import DatasetRegistry
from src.data.scope import use_for as _use_for_role
from src.data.scope import use_counts as _use_counts
from src.utils.paths import OUTPUTS_DIR


st.set_page_config(
    page_title="PARIVARTANA",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_global_styles()
render_sidebar("Home")


DATASET_USE_get = _use_for_role


def _provider_status() -> dict[str, bool]:
    return {
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
    }


def _hf_token_loaded() -> bool:
    return bool(os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN"))


def _count_conversions() -> int:
    conv_dir = OUTPUTS_DIR / "conversions"
    if not conv_dir.exists():
        return 0
    return sum(1 for p in conv_dir.glob("*.json"))


def _sample_count() -> int:
    samples_dir = ROOT / "data" / "samples"
    if not samples_dir.exists():
        return 0
    return sum(1 for _ in samples_dir.glob("*.cob"))


def _verifier_readiness() -> dict[str, bool]:
    return {
        "structural": True,                    
        "execution": shutil.which("cobc") is not None,
        "llm_judge": any(_provider_status().values()),
    }


def main() -> None:
    render_page_header(
        eyebrow="HOME",
        title="PARIVARTANA",
        subtitle="COBOL-to-Python neural transpiler with NLI semantic validation.",
    )

                                                                        
    registry = DatasetRegistry()
    rows = registry.status_table()
    present_rows = [r for r in rows if r["present"]]
    present = len(present_rows)
    total = len(rows)
    coverage_pct = (present / total * 100) if total else 0

                                                                    
    present_specs = [registry.get(r["key"]) for r in present_rows]
    use_counts = _use_counts(present_specs)

    providers = _provider_status()
    provider_count = sum(1 for v in providers.values() if v)
    hf_loaded = _hf_token_loaded()
    conv_count = _count_conversions()
    sample_count = _sample_count()
    verifier = _verifier_readiness()

                                                                        
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Pipeline stages", "3 / 3", "live")
    c2.metric(
        "Datasets present",
        f"{present}/{total}",
        f"{coverage_pct:.0f}% coverage",
    )
    c3.metric(
        "Train / Test",
        f"{use_counts['TRAIN']} / {use_counts['TEST']}",
        f"+{use_counts['SUPPORT']} support",
    )
    c4.metric("LLM providers", f"{provider_count}/2")
    c5.metric("HF token", "loaded" if hf_loaded else "missing")
    c6.metric("Saved conversions", str(conv_count))

    st.markdown("<div class='pv-divider'></div>", unsafe_allow_html=True)

                                                                        
    st.markdown("**Pipeline**")
    stages = [
        StageStatus(
            number=1,
            name="Preprocessor",
            description="Fixed-format stripping, recursive-descent parser, complexity tiering.",
            state="production",
            state_label="Live",
        ),
        StageStatus(
            number=2,
            name="Neural Translation",
            description="Rule-based AST templater (baseline) and CodeT5+ neural path with curriculum trainer.",
            state="production",
            state_label="Live",
        ),
        StageStatus(
            number=3,
            name="LLM Refinement",
            description="Dictionary rename, GPT-4 / Claude rewrite, docstring synthesis, DeBERTa NLI semantic check.",
            state="production",
            state_label="Live",
        ),
    ]
    render_stage_status(stages)

                                                                        
    st.markdown("**Quick actions**")
    a1, a2, a3 = st.columns(3)
    with a1:
        st.markdown(
            f"""
            <div class="pv-card">
                <p class="pv-card-title">Transpile a single program</p>
                {badge('All stages live', 'success')}
                <p style='color:#64748B;font-size:0.85rem;margin:0.6rem 0 0 0;'>
                    Side-by-side viewer with AST tree, semantic verdict, and verifier report.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.page_link("pages/1_Workspace.py", label="Workspace →")

    with a2:
        st.markdown(
            f"""
            <div class="pv-card">
                <p class="pv-card-title">Batch over a corpus</p>
                {badge('Stages 1 → 2 → 3 per program', 'primary')}
                <p style='color:#64748B;font-size:0.85rem;margin:0.6rem 0 0 0;'>
                    Expandable cards with AST tree and collapsible stage outputs.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.page_link("pages/2_Batch_Run.py", label="Batch Run →")

    with a3:
        ingest_kind = "success" if present else "warning"
        ingest_label = f"{present}/{total} present" if total else "no datasets registered"
        st.markdown(
            f"""
            <div class="pv-card">
                <p class="pv-card-title">Data and training</p>
                {badge(ingest_label, ingest_kind)}
                <p style='color:#64748B;font-size:0.85rem;margin:0.6rem 0 0 0;'>
                    Ingest corpora, then run the curriculum trainer dry-run on real tier distribution.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.page_link("pages/3_Datasets.py", label="Datasets →")

    st.markdown("<div class='pv-divider'></div>", unsafe_allow_html=True)

                                                                        
    st.markdown("**Verifier readiness**")
    st.caption(
        "Which checks the verifier on the Workspace page can actually run. "
        "Behavioural signals (execution match, LLM judge) are needed to push "
        "the verdict from INCONCLUSIVE to PASS."
    )
    v1, v2, v3 = st.columns(3)
    v1.markdown(
        badge("Structural · ready", "success") + " &nbsp; "
        + "<span style='color:#64748B;font-size:0.85rem;'>syntax, paragraph coverage, identifier coverage</span>",
        unsafe_allow_html=True,
    )
    v2.markdown(
        (badge("Execution · ready", "success") if verifier["execution"]
         else badge("Execution · install GnuCOBOL", "warning"))
        + " &nbsp; "
        + "<span style='color:#64748B;font-size:0.85rem;'>compile COBOL with cobc, compare stdout</span>",
        unsafe_allow_html=True,
    )
    v3.markdown(
        (badge("LLM judge · ready", "success") if verifier["llm_judge"]
         else badge("LLM judge · set API key", "warning"))
        + " &nbsp; "
        + "<span style='color:#64748B;font-size:0.85rem;'>5-dimension rubric scored by GPT-4 or Claude</span>",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='pv-divider'></div>", unsafe_allow_html=True)

                                                                        
    st.markdown("**System health**")

    def _ok(ok: bool) -> str:
        return "operational" if ok else "needs configuration"

    rows_health = [
        {
            "Component": "Stage 1 — preprocessor & complexity tiering",
            "Status": "operational",
            "Notes": f"{sample_count} bundled sample program(s)",
        },
        {
            "Component": "Stage 2 — rule-based templater (Method 1 baseline)",
            "Status": "operational",
            "Notes": "deterministic; fallback path when neural unavailable",
        },
        {
            "Component": "Stage 2 — CodeT5+ neural translator",
            "Status": "operational",
            "Notes": "off-the-shelf weights; fine-tune the curriculum on Datasets → Train to improve",
        },
        {
            "Component": "Stage 3 — dictionary rename + LLM refine + NLI validator",
            "Status": _ok(provider_count > 0),
            "Notes": "OpenAI or Anthropic key needed for LLM rewrite; NLI falls back to lexical Jaccard",
        },
        {
            "Component": "Verifier (execution accuracy)",
            "Status": _ok(verifier["execution"]),
            "Notes": "install GnuCOBOL (cobc) to enable behavioural pass/fail",
        },
        {
            "Component": "Dataset registry",
            "Status": _ok(present > 0),
            "Notes": f"{present}/{total} datasets ingested locally",
        },
        {
            "Component": "Conversion history",
            "Status": "operational",
            "Notes": f"{conv_count} saved record(s) under artifacts/outputs/conversions/",
        },
    ]
    st.dataframe(rows_health, width="stretch", hide_index=True)


main()
