
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.conversion_history import (
    CONVERSIONS_DIR,
    ConversionRecord,
    clear_all,
    list_conversions,
    load_conversion,
    new_record_id,
    save_conversion,
)
from app.ast_view import render_ast_tree
from app.python_ast_view import render_python_ast
from app.theme import (
    badge,
    inject_global_styles,
    render_page_header,
    render_sidebar,
)
from src.evaluation.verifier import VerificationReport, verify
from src.pipeline.stage1_parser import CobolParser, ComplexityScorer
from src.pipeline.stage2_neural.rule_based import RuleBasedTranslator
from src.pipeline.stage3_llm.providers import AnthropicProvider, OpenAIProvider
from src.pipeline.stage3_llm.refiner import LLMRefiner

st.set_page_config(page_title="Workspace - PARIVARTANA", layout="wide")
inject_global_styles()

SAMPLES_DIR = ROOT / "data" / "samples"


def _load_sample(name: str) -> str:
    path = SAMPLES_DIR / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _provider_available(name: str) -> bool:
    if name == "openai":
        return OpenAIProvider().is_available()
    if name == "anthropic":
        return AnthropicProvider().is_available()
    return False


def _tier_kind(tier: str) -> str:
    return {"simple": "success", "medium": "warning", "high": "danger"}.get(tier, "neutral")


def _semantic_kind(label: str) -> str:
    return {
        "SUPPORTED": "success",
        "REFUTED": "danger",
        "NEI": "warning",
    }.get(label, "neutral")


def _fmt_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _run_verification(
    cobol_source: str,
    python_source: str,
    ast,
    provider_name: str,
    run_llm_judge: bool,
) -> dict:
    try:
        report: VerificationReport = verify(
            cobol_source=cobol_source,
            python_source=python_source,
            ast=ast,
            run_execution=True,
            run_llm_judge=run_llm_judge,
            llm_provider=provider_name,
        )
        return report.to_dict()
    except Exception as exc:                
        return {"verdict": "INCONCLUSIVE", "summary": f"Verifier crashed: {exc}", "checks": []}


def _find_inline_comment(source: str) -> str:
    for raw in source.splitlines():
        line = raw.rstrip()
        if not line:
            continue
                                                                   
                                                                    
        if len(line) >= 7 and line[6] == "*":
            body = line[7:].strip()
            if body:
                return body
                                     
        if "*>" in line:
            body = line.split("*>", 1)[1].strip()
            if body:
                return body
                                                                            
        stripped = line.lstrip()
        if stripped.startswith("*") and not stripped.startswith("*>"):
            body = stripped.lstrip("*").strip()
            if body:
                return body
    return ""


def _render_history_controls(records: list[ConversionRecord]) -> str | None:
    if not records and not st.session_state.get("confirm_clear"):
        return None

    selected_id: str | None = None
    col_pick, col_clear = st.columns([4, 1])

    with col_pick:
        if records:
            options = ["(latest)"] + [
                f"{r.program_id} · {_fmt_ts(r.created_at)} · {r.tier.title()}"
                for r in records[:50]
            ]
            choice = st.selectbox(
                f"History — {len(records)} saved",
                options=options,
                index=0,
                key="history_picker",
            )
            if choice != "(latest)":
                idx = options.index(choice) - 1
                selected_id = records[idx].record_id

    with col_clear:
        st.write("")                                           
        if st.session_state.get("confirm_clear"):
            if st.button("Confirm clear", type="primary", key="confirm_yes", width="stretch"):
                removed = clear_all()
                st.session_state["confirm_clear"] = False
                st.session_state.pop("current_record_id", None)
                st.session_state.pop("history_picker", None)
                st.toast(f"Cleared {removed} conversion(s)")
                st.rerun()
            if st.button("Cancel", key="confirm_no", width="stretch"):
                st.session_state["confirm_clear"] = False
                st.rerun()
        else:
            if st.button(
                "Clear history",
                key="clear_history",
                width="stretch",
                disabled=not records,
            ):
                st.session_state["confirm_clear"] = True
                st.rerun()

    return selected_id


def _run_pipeline(
    cobol_source: str,
    run_stage3: bool,
    provider_name: str,
) -> ConversionRecord | None:
    parser = CobolParser()
    scorer = ComplexityScorer()

    t0 = time.perf_counter()
    parse = parser.parse(cobol_source)
    s1_ms = (time.perf_counter() - t0) * 1000

    if not parse.ok or parse.ast is None:
        st.error(f"Parsing failed with {len(parse.errors)} error(s).")
        for err in parse.errors:
            st.markdown(f"- Line **{err.line}**, column {err.column}: {err.message}")
        return None

    score = scorer.score(parse.ast)

                                                        
    t0 = time.perf_counter()
    rule_based = RuleBasedTranslator().translate(parse.ast)
    rule_based_ms = (time.perf_counter() - t0) * 1000

    neural_python: str | None = None
    neural_ms = 0.0
    fallback_used = False
    raw_python = rule_based.code

                                                                        
    refined_python = raw_python
    semantic_label = "not_run"
    semantic_conf: float | None = None
    semantic_source: str | None = None
    rename_count = 0
    pipeline_steps: list[str] = []
    s3_ms = 0.0

    if run_stage3:
        identifiers = sorted(
            {
                n.attributes["name"]
                for n in parse.ast.walk()
                if n.node_type == "DataItem" and "name" in n.attributes
            }
        )
                                                                      
                                                                        
        first_comment = _find_inline_comment(cobol_source)

        refiner = LLMRefiner(provider=provider_name)
        t0 = time.perf_counter()
        ref_result = refiner.refine(
            raw_python=raw_python,
            tier=score.tier,
            cobol_identifiers=identifiers,
            cobol_comment=first_comment,
            run_semantic_check=bool(first_comment),
            run_docstring_synthesis=_provider_available(provider_name),
            cobol_source=cobol_source,
        )
        s3_ms = (time.perf_counter() - t0) * 1000
        refined_python = ref_result.refined_python
        if ref_result.semantic_check is not None:
            semantic_label = ref_result.semantic_check.label.value
            semantic_conf = ref_result.semantic_check.confidence
            semantic_source = ref_result.semantic_check.source
        rename_count = ref_result.rename_count
        pipeline_steps = list(ref_result.metadata.get("pipeline_steps", []))

    record = ConversionRecord(
        record_id=new_record_id(),
        created_at=time.time(),
        program_id=parse.program_id or "(unnamed)",
        tier=score.tier.value,
        complexity_score=score.raw_score,
        cobol_source=cobol_source,
        rule_based_python=rule_based.code,
        neural_python=neural_python,
        refined_python=refined_python,
        semantic_label=semantic_label,
        semantic_confidence=semantic_conf,
        semantic_source=semantic_source,
        rename_count=rename_count,
        pipeline_steps=pipeline_steps,
        stage_timings_ms={
            "stage1_parse": round(s1_ms, 2),
            "stage2_rule_based": round(rule_based_ms, 2),
            "stage2_neural": round(neural_ms, 2),
            "stage3_refine": round(s3_ms, 2),
        },
        provider=provider_name if run_stage3 else "",
        fallback_used=fallback_used,
        extra={
            "ast_depth": score.ast_depth,
            "unique_verb_count": score.unique_verb_count,
            "cross_ref_count": score.cross_ref_count,
            "high_tier_flag": score.high_tier_flag,
            "paragraph_count": parse.paragraph_count,
            "division_count": parse.division_count,
            "ast_tree": render_ast_tree(parse.ast),
            "verification": _run_verification(
                cobol_source=cobol_source,
                python_source=refined_python,
                ast=parse.ast,
                provider_name=provider_name if run_stage3 else "openai",
                run_llm_judge=run_stage3 and _provider_available(provider_name),
            ),
        },
    )
    save_conversion(record)
    st.session_state["current_record_id"] = record.record_id
    return record


def _render_record(record: ConversionRecord) -> None:
    st.markdown("<div class='pv-divider'></div>", unsafe_allow_html=True)

                  
    st.markdown(
        f"<p style='margin: 0 0 0.4rem 0;'>"
        f"<strong>{record.program_id}</strong> &middot; "
        f"{badge(record.tier.title(), _tier_kind(record.tier))} &middot; "
        f"{badge(record.semantic_label, _semantic_kind(record.semantic_label))} &middot; "
        f"<span style='color:#64748B;font-size:0.85rem'>"
        f"saved {_fmt_ts(record.created_at)}</span>"
        f"</p>",
        unsafe_allow_html=True,
    )

                                                                        
    verification = record.extra.get("verification") or {}
    verdict = verification.get("verdict", "—")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Verdict", verdict)
    m2.metric("Tier", record.tier.title())
    m3.metric("Complexity", f"{record.complexity_score:.1f}")
    m4.metric("Stage 1", f"{record.stage_timings_ms.get('stage1_parse', 0):.1f} ms")
    m5.metric(
        "Stage 2",
        f"{record.stage_timings_ms.get('stage2_neural') or record.stage_timings_ms.get('stage2_rule_based', 0):.1f} ms",
    )
    m6.metric("Stage 3", f"{record.stage_timings_ms.get('stage3_refine', 0):.1f} ms")

    if record.fallback_used:
        st.markdown(
            badge("Stage 2 used rule-based fallback (no neural checkpoint reachable)", "warning"),
            unsafe_allow_html=True,
        )

                         
    st.markdown("##### Side-by-side")
    left, right = st.columns(2)
    with left:
        st.caption("COBOL source")
        st.code(record.cobol_source, language="cobol")
    with right:
        st.caption("Refined Python (final)")
        st.code(record.refined_python, language="python")

                                                     
    tab_verify, tab_ast, tab_stage3, tab_raw = st.tabs(
        ["Verify", "AST tree", "Stage 3 detail", "Raw record"]
    )

    with tab_verify:
        verification = record.extra.get("verification")
        if not verification:
            st.caption("This conversion was saved before the verifier was wired in. Run a fresh transpile to see verification results.")
        else:
            verdict = verification.get("verdict", "INCONCLUSIVE")
            verdict_kind = {
                "PASS": "success",
                "STRUCTURAL_PASS": "success",
                "FAIL": "danger",
                "INCONCLUSIVE": "warning",
            }.get(verdict, "neutral")
            st.markdown(
                f"### {badge(verdict, verdict_kind)} &nbsp; "
                f"<span style='color:#0F172A;font-weight:600;'>{verification.get('summary','')}</span>",
                unsafe_allow_html=True,
            )
            st.caption(
                "Verdict logic: PASS = at least one behavioural check (execution match or "
                "LLM judge) passed and no check failed. STRUCTURAL_PASS = all four structural "
                "checks passed AND behavioural signals were unavailable for environment reasons "
                "(no API key, cobc missing). FAIL = any check returned a hard failure. "
                "INCONCLUSIVE = checks didn't run or a behavioural signal was needed but not "
                "even attempted."
            )
            for c in verification.get("checks", []):
                if not c.get("ran"):
                    st.markdown(
                        f"- {badge('SKIP', 'neutral')} &nbsp; **{c['name']}** — "
                        f"<span style='color:#64748B;'>{c.get('skipped_reason','')}</span>",
                        unsafe_allow_html=True,
                    )
                    continue
                passed = c.get("passed")
                kind = "success" if passed else "danger"
                label = "PASS" if passed else "FAIL"
                score_str = ""
                if c.get("score") is not None:
                    score_str = f" &middot; score `{c['score']:.2f}`"
                st.markdown(
                    f"- {badge(label, kind)} &nbsp; **{c['name']}**{score_str} — "
                    f"<span style='color:#475569;'>{c.get('detail','')}</span>",
                    unsafe_allow_html=True,
                )
                                                          
                if c["name"] == "execution_match" and c.get("extra"):
                    with st.expander("stdout diff"):
                        col_l, col_r = st.columns(2)
                        col_l.caption("COBOL stdout")
                        col_l.code(c["extra"].get("cobol_stdout", ""), language="text")
                        col_r.caption("Python stdout")
                        col_r.code(c["extra"].get("python_stdout", ""), language="text")
                                                        
                if c["name"] == "llm_judge" and c.get("extra", {}).get("rationale"):
                    with st.expander("Judge rationale"):
                        st.write(c["extra"]["rationale"])

    with tab_ast:
                                                                 
                                                                   
        cobol_ast_text = record.extra.get("ast_tree", "")
        python_ast_text = render_python_ast(record.refined_python or "")

        a1, a2, a3, a4, a5 = st.columns(5)
        a1.metric("Verifier verdict", verdict)
        a2.metric("AST depth", record.extra.get("ast_depth", 0))
        a3.metric("Unique verbs", record.extra.get("unique_verb_count", 0))
        a4.metric("Divisions", record.extra.get("division_count", 0))
        a5.metric("Paragraphs", record.extra.get("paragraph_count", 0))

        st.caption(
            "Stage 1 — COBOL AST on the left feeds the curriculum tier signal. "
            "Python AST on the right is parsed from the refined output and lets "
            "you eyeball whether the structure was preserved."
        )
        ast_cobol_col, ast_py_col = st.columns(2)
        with ast_cobol_col:
            st.caption("COBOL AST")
            st.code(cobol_ast_text or "(none)", language="text")
        with ast_py_col:
            st.caption("Python AST (refined output)")
            st.code(python_ast_text or "(none)", language="text")

    with tab_stage3:
        if record.semantic_label == "not_run":
            st.caption("Stage 3 was not executed for this conversion.")
        else:
            kind = _semantic_kind(record.semantic_label)
            conf = f"{record.semantic_confidence:.2f}" if record.semantic_confidence is not None else "—"
            st.markdown(
                f"**Semantic check:** {badge(record.semantic_label, kind)} "
                f"&nbsp;&middot;&nbsp; confidence `{conf}` "
                f"&nbsp;&middot;&nbsp; source `{record.semantic_source or '—'}`",
                unsafe_allow_html=True,
            )
            st.metric("Renames applied", record.rename_count)
            if record.provider:
                st.caption(f"Provider: `{record.provider}`")
            if record.pipeline_steps:
                st.caption("Pipeline trace")
                for step in record.pipeline_steps:
                    st.markdown(f"- `{step}`")

    with tab_raw:
        st.json(record.to_dict(), expanded=False)


def main() -> None:
    render_sidebar("Workspace")

    render_page_header(
        eyebrow="WORKSPACE",
        title="Transpile",
        subtitle="Run a COBOL program through Stages 1–3 and inspect the conversion.",
    )

                                                                   
    records = list_conversions()
    selected_id = _render_history_controls(records)
    if selected_id:
        st.session_state["current_record_id"] = selected_id

    samples = sorted(p.name for p in SAMPLES_DIR.glob("*.cob"))
    col_input, col_options = st.columns([3, 2])

    with col_input:
        st.markdown("**Source**")
        source_mode = st.radio(
            "Input mode",
            options=["Sample", "Paste", "Upload"],
            horizontal=True,
            label_visibility="collapsed",
        )

        cobol_source = ""
        if source_mode == "Sample":
            chosen = st.selectbox("Sample", options=samples, label_visibility="collapsed")
            if chosen:
                cobol_source = _load_sample(chosen)
        elif source_mode == "Paste":
            cobol_source = st.text_area(
                "COBOL source",
                height=320,
                placeholder="Paste fixed-format COBOL.",
                label_visibility="collapsed",
            )
        else:
            uploaded = st.file_uploader(
                "Upload",
                type=["cob", "cbl", "cobol", "cpy", "txt"],
                label_visibility="collapsed",
            )
            if uploaded is not None:
                cobol_source = uploaded.read().decode("utf-8", errors="replace")

        if cobol_source:
            with st.expander("Preview", expanded=False):
                st.code(cobol_source, language="cobol")

    with col_options:
        st.markdown("**Options**")
        run_stage3 = st.toggle("Stage 3 LLM refinement", value=True)
        provider_name = st.selectbox(
            "Provider",
            options=["openai", "anthropic"],
            disabled=not run_stage3,
        )
        provider_ok = _provider_available(provider_name)
        st.markdown(
            badge("Available", "success") if provider_ok else badge("Key missing — rename only", "warning"),
            unsafe_allow_html=True,
        )

        st.write("")
        run_clicked = st.button(
            "Transpile",
            type="primary",
            disabled=not cobol_source,
            width="stretch",
        )

    if run_clicked and cobol_source:
        with st.spinner("Running pipeline..."):
            record = _run_pipeline(
                cobol_source=cobol_source,
                run_stage3=run_stage3,
                provider_name=provider_name,
            )
        if record is not None:
            _render_record(record)
        return

                                                                        
    current_id = st.session_state.get("current_record_id")
    record: ConversionRecord | None = None
    if current_id:
        record = load_conversion(current_id)
    if record is None:
        records = list_conversions()
        record = records[0] if records else None

    if record is not None:
        _render_record(record)
    else:
        st.info("Run a transpile or pick a sample to see the side-by-side view.")


main()
