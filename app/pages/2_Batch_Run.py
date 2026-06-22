
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ast_view import render_ast_tree
from app.python_ast_view import render_python_ast
from app.theme import (
    badge,
    empty_state,
    inject_global_styles,
    render_page_header,
    render_sidebar,
)
from src.data.loaders import ALL_LOADERS
from src.data.registry import DatasetRegistry
from src.evaluation.verifier import verify
from src.pipeline.stage1_parser import CobolParser, ComplexityScorer
from src.pipeline.stage2_neural.checkpoint_registry import load_latest
from src.pipeline.stage2_neural.rule_based import RuleBasedTranslator
from src.pipeline.stage2_neural.translator import NeuralTranslator
from src.pipeline.stage3_llm.providers import AnthropicProvider, OpenAIProvider, get_provider
from src.pipeline.stage3_llm.refiner import LLMRefiner
from src.pipeline.stage3_llm.rescue import rescue_translation
from src.utils.io import write_json
from src.utils.paths import OUTPUTS_DIR, RUNS_DIR, ensure_dir
from src.evaluation.stage_trace import build_trace_from_row, write_trace

st.set_page_config(page_title="Batch Run - PARIVARTANA", layout="wide")
inject_global_styles()
render_sidebar("Batch Run")


COBOL_DATASETS = {"nist_cobol", "ibm_open_cobol", "stack_v2_cobol", "gfg_multilingual"}


def _provider_available(name: str) -> bool:
    if name == "openai":
        return OpenAIProvider().is_available()
    if name == "anthropic":
        return AnthropicProvider().is_available()
    return False


def _provider_chain(preferred: str) -> list[str]:
    chain: list[str] = []
    if _provider_available(preferred):
        chain.append(preferred)
    for alt in ("openai", "anthropic"):
        if alt != preferred and _provider_available(alt) and alt not in chain:
            chain.append(alt)
    return chain


def _tier_kind(tier: str) -> str:
    return {"simple": "success", "medium": "warning", "high": "danger"}.get(tier, "neutral")


def _verdict_kind(verdict: str) -> str:
                                                                    
                                                             
    return {
        "PASS": "success",
        "STRUCTURAL_PASS": "success",
        "FAIL": "danger",
        "INCONCLUSIVE": "warning",
    }.get(verdict, "neutral")


def _line_count(code: str) -> int:
    return len([ln for ln in (code or "").splitlines() if ln.strip()])


def _runnable_datasets(registry: DatasetRegistry) -> list[dict]:
    rows = []
    for spec in registry.all():
        if spec.key not in COBOL_DATASETS:
            continue
        rows.append(
            {
                "key": spec.key,
                "name": spec.name,
                "samples": spec.samples,
                "present": spec.exists_locally(),
                "files": spec.file_count(),
                "spec": spec,
            }
        )
    return rows


def _process_record(
    rec: dict,
    parser: CobolParser,
    scorer: ComplexityScorer,
    translator: RuleBasedTranslator,
    refiner: LLMRefiner | None,
    rescue_provider_name: str | None = None,
    neural: NeuralTranslator | None = None,
    run_execution: bool = False,
    run_llm_judge: bool = False,
    judge_provider: str | list[str] = "openai",
) -> dict:
    source = rec.get("source") or rec.get("content") or ""
    record_id = rec.get("id") or rec.get("instance_id") or "(unknown)"

    parse = parser.parse(source)
    if not parse.ok or parse.ast is None:
        return {
            "id": record_id,
            "ok": False,
            "tier": None,
            "complexity": None,
            "cobol_source": source,
            "ast_tree": "",
            "rule_based_python": "",
            "refined_python": "",
            "semantic_label": None,
            "verdict": "FAIL",
            "verdict_summary": f"Stage 1 parse failed ({len(parse.errors)} errors)",
            "verdict_checks": [],
            "errors": [f"L{e.line}:{e.column} {e.message}" for e in parse.errors],
            "ast_obj": None,
            "stage1_program_id": parse.program_id or "",
            "stage1_division_count": parse.division_count,
            "stage1_paragraph_count": parse.paragraph_count,
            "stage1_token_count": len(parse.tokens),
            "stage1_warnings": list(parse.warnings or []),
        }

    score = scorer.score(parse.ast)
    rule_based = translator.translate(parse.ast)
                                                                    
                                                                        
    import ast as _pyast

    def _strip_markdown_fences(text: str) -> str:
        t = (text or "").strip()
        if not t.startswith("```"):
            return t
        lines = t.splitlines()
        if lines and lines[0].lstrip("`").lower().startswith(("python", "py", "")):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()

                                                                        
    neural_python = ""
    neural_parses = False
    if neural is not None:
        neural_result = neural.translate(parse.ast, score.tier)
        neural_python = _strip_markdown_fences(neural_result.python_code)
        try:
            _pyast.parse(neural_python)
            neural_parses = bool(neural_python.strip())
        except SyntaxError:
            neural_parses = False

                                                                        
    rescue_status: str | None = None
    if neural is not None and neural_parses:
        stage2_python = neural_python
        stage2_source = "neural"
    elif neural is not None and neural_python and rescue_provider_name:
                                                                     
        try:
            prov = get_provider(rescue_provider_name)
        except Exception:                
            prov = None
        if prov is not None and prov.is_available():
            rescue_result = rescue_translation(
                cobol_source=source,
                broken_python=neural_python,
                provider=prov,
            )
            if rescue_result.valid:
                stage2_python = rescue_result.python_source
                stage2_source = "rescued"
                rescue_status = f"rescued in {rescue_result.rounds} round(s)"
            else:
                                                                    
                                                                  
                stage2_python = rule_based.code
                stage2_source = "rule-based-fallback"
                rescue_status = f"rescue failed: {rescue_result.error}"
        else:
            stage2_python = rule_based.code
            stage2_source = "rule-based-fallback"
            rescue_status = f"rescue skipped: {rescue_provider_name} key missing"
    elif neural is not None and neural_python:
                                                                          
        stage2_python = rule_based.code
        stage2_source = "rule-based-fallback"
        rescue_status = "neural output unparseable; rule-based fallback used"
    else:
                                                                   
        stage2_python = rule_based.code
        stage2_source = "rule-based"

    refined_python = ""
    semantic_label: str | None = None
    if refiner is not None:
        identifiers = sorted(
            {
                n.attributes["name"]
                for n in parse.ast.walk()
                if n.node_type == "DataItem" and "name" in n.attributes
            }
        )
        try:
            result = refiner.refine(
                raw_python=stage2_python,                             
                tier=score.tier,
                cobol_identifiers=identifiers,
                cobol_comment="",                                                       
                run_semantic_check=False,
                run_docstring_synthesis=False,
                cobol_source=source,                                              
            )
            refined_python = result.refined_python
            if result.semantic_check is not None:
                semantic_label = result.semantic_check.label.value
        except Exception as exc:                
            refined_python = f"# Stage 3 failed: {exc}\n" + rule_based.code

                                                                 
    eval_target = refined_python or stage2_python
    try:
        report = verify(
            cobol_source=source,
            python_source=eval_target,
            ast=parse.ast,
            run_execution=run_execution,
            run_llm_judge=run_llm_judge,
            llm_provider=judge_provider,
        )
        verdict = report.verdict
        verdict_summary = report.summary
        verdict_checks = [
            {
                "name": c.name,
                "ran": c.ran,
                "passed": c.passed,
                "score": c.score,
                "detail": c.detail,
                "skipped_reason": c.skipped_reason,
            }
            for c in report.checks
        ]
                                                                     
                                                                    
        if verdict == "INCONCLUSIVE":
            judge_check = next((c for c in report.checks if c.name == "llm_judge"), None)
            if judge_check is not None and not judge_check.ran and judge_check.skipped_reason:
                verdict_summary = (
                    f"{verdict_summary} llm_judge skipped: {judge_check.skipped_reason}"
                )
    except Exception as exc:                
        verdict = "INCONCLUSIVE"
        verdict_summary = f"verifier crashed: {exc}"
        verdict_checks = []

    return {
        "id": record_id,
        "ok": True,
        "tier": score.tier.value,
        "complexity": round(score.raw_score, 2),
        "ast_depth": score.ast_depth,
        "verbs": score.unique_verb_count,
        "cross_refs": score.cross_ref_count,
        "high_tier_flag": score.high_tier_flag,
        "program_id": parse.program_id or "(unnamed)",
        "cobol_source": source,
        "ast_tree": render_ast_tree(parse.ast),
        "rule_based_python": stage2_python,
        "rule_based_python_original": rule_based.code,
        "neural_python": neural_python,
        "stage2_source": stage2_source,
        "rescue_status": rescue_status,
        "stage2_warnings": list(rule_based.warnings or []),
        "refined_python": refined_python,
        "semantic_label": semantic_label,
        "verdict": verdict,
        "verdict_summary": verdict_summary,
        "verdict_checks": verdict_checks,
        "errors": [],
        "ast_obj": parse.ast,
        "stage1_program_id": parse.program_id or "",
        "stage1_division_count": parse.division_count,
        "stage1_paragraph_count": parse.paragraph_count,
        "stage1_token_count": len(parse.tokens),
        "stage1_warnings": list(parse.warnings or []),
        "stage3_provider": (refiner.provider.name if refiner is not None and hasattr(refiner, "provider") else ""),
    }


def _render_card(row: dict, run_stage3: bool, idx: int) -> None:
    if not row["ok"]:
                                                                      
        st.markdown(
            f"<div class='pv-card' style='padding:0.7rem 1rem;'>"
            f"<strong>{row['program_id']}</strong> · `{row['id']}` &nbsp; "
            f"{badge('Parse failed', 'danger')} &nbsp; "
            f"<span style='color:#64748B;font-size:0.85rem;'>"
            f"{row.get('verdict_summary','')}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        with st.expander("Error detail", expanded=False):
            for e in row["errors"]:
                st.code(e)
        return

    tier = row["tier"]
    verdict = row.get("verdict", "INCONCLUSIVE")
    s2_lines = _line_count(row.get("rule_based_python", ""))
    s3_lines = _line_count(row.get("refined_python", ""))
    semantic_label = row.get("semantic_label")

                                                                        
    s1_html = f"Stage 1: {badge('parsed', 'success')} <span style='color:#64748B;font-size:0.85rem;'>complexity {row['complexity']}</span>"
    rescue_badge = ""
    if row.get("rescue_status"):
        kind = "success" if row["rescue_status"].startswith("rescued") else "warning"
        short = "rescued" if row["rescue_status"].startswith("rescued") else "rescue skipped"
        rescue_badge = f" {badge(short, kind)}"

                                                                        
    src = row.get("stage2_source") or "rule-based"
    src_kind = {
        "neural": "primary",
        "rescued": "success",
        "neural-fallback": "warning",
        "rule-based-fallback": "warning",
        "rule-based": "neutral",
    }.get(src, "neutral")
    source_badge = f" {badge(src, src_kind)}"
    s2_html = f"Stage 2: <span style='color:#0F172A;'>{s2_lines} lines</span>{source_badge}{rescue_badge}"
    if run_stage3 and row.get("refined_python"):
        sem_part = f" · {badge(semantic_label, 'neutral')}" if semantic_label and semantic_label != "not_run" else ""
        s3_html = f"Stage 3: <span style='color:#0F172A;'>{s3_lines} lines</span>{sem_part}"
    elif run_stage3:
        s3_html = f"Stage 3: {badge('skipped', 'neutral')}"
    else:
        s3_html = f"Stage 3: <span style='color:#64748B;'>not run</span>"

                                                                     
    st.markdown(
        f"""
        <div class='pv-card' style='padding:0.7rem 1rem 0.8rem 1rem;'>
            <div style='display:flex;gap:0.6rem;align-items:center;flex-wrap:wrap;'>
                <strong style='font-size:0.95rem;'>{row['program_id']}</strong>
                <span style='color:#64748B;font-size:0.8rem;'>{row['id']}</span>
                {badge(tier.title(), _tier_kind(tier))}
                {badge(verdict, _verdict_kind(verdict))}
            </div>
            <div style='margin-top:0.5rem;display:flex;gap:1.5rem;flex-wrap:wrap;font-size:0.9rem;'>
                <span>{s1_html}</span>
                <span>{s2_html}</span>
                <span>{s3_html}</span>
            </div>
            <div style='color:#64748B;font-size:0.8rem;margin-top:0.35rem;'>
                {row.get('verdict_summary','')}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Show stage outputs", expanded=False):
                                                                 
        cA, cB, cC, cD, cE = st.columns(5)
        cA.metric("Verdict", verdict)
        cB.metric("Complexity", row["complexity"])
        cC.metric("AST depth", row["ast_depth"])
        cD.metric("Unique verbs", row["verbs"])
        cE.metric("Cross-refs", row["cross_refs"])

                                                    
        cobol_col, ast_col = st.columns(2)
        with cobol_col:
            st.caption("COBOL source")
            st.code(row["cobol_source"], language="cobol")
        with ast_col:
            st.caption("Stage 1 — COBOL AST")
            st.code(row["ast_tree"], language="text")

                                                                       
        py_source = row.get("refined_python") or row.get("rule_based_python") or ""
        st.caption("Python AST (parsed from the translated output)")
        st.code(render_python_ast(py_source), language="text")

                                                
        show_s2 = st.checkbox(
            f"Stage 2 — rule-based Python ({s2_lines} lines)",
            value=True,
            key=f"s2_{idx}_{row['id']}",
        )
        if show_s2:
            st.code(row["rule_based_python"], language="python")

                                                     
        if run_stage3 and row["refined_python"]:
            stage3_label = f"Stage 3 — refined Python ({s3_lines} lines)"
            if semantic_label and semantic_label != "not_run":
                stage3_label += f" — semantic: {semantic_label}"
            show_s3 = st.checkbox(
                stage3_label,
                value=True,
                key=f"s3_{idx}_{row['id']}",
            )
            if show_s3:
                st.code(row["refined_python"], language="python")
        elif run_stage3:
            st.caption("Stage 3 — no refined output (provider unavailable or refiner skipped).")

                                    
        if row.get("verdict_checks"):
            st.markdown("---")
            st.caption("Verifier breakdown (structural — execution + LLM judge are skipped in batch mode)")
            for c in row["verdict_checks"]:
                if not c.get("ran"):
                    continue
                kind = "success" if c["passed"] else "danger"
                label = "PASS" if c["passed"] else "FAIL"
                score = f" `{c['score']:.2f}`" if c.get("score") is not None else ""
                st.markdown(
                    f"- {badge(label, kind)} &nbsp; **{c['name']}**{score} — "
                    f"<span style='color:#475569;'>{c.get('detail','')}</span>",
                    unsafe_allow_html=True,
                )


def main() -> None:
    render_page_header(
        eyebrow="BATCH RUN",
        title="Batch transpile",
        subtitle="Run Stages 1 → 2 → (3) on N programs from a corpus and inspect every stage.",
    )

    registry = DatasetRegistry()
    runnable = _runnable_datasets(registry)
    available = [r for r in runnable if r["present"]]

    if not available:
        empty_state(
            title="No COBOL datasets ingested",
            description="Open the Datasets page and click 'Load and prepare data' first.",
            action_label="Datasets",
            action_target="/Datasets",
        )
        return

    col_ds, col_n, col_s3 = st.columns([2, 1, 1])
    with col_ds:
        dataset_key = st.selectbox(
            "Dataset",
            options=[r["key"] for r in available],
            format_func=lambda k: registry.get(k).name,
        )
    with col_n:
        max_records = st.number_input("Programs to process", min_value=1, max_value=200, value=10, step=1)
    with col_s3:
        _s3_default = _provider_available("openai") or _provider_available("anthropic")
        run_stage3 = st.toggle(
            "Run Stage 3",
            value=_s3_default,
            help=(
                "LLM refinement of the Stage-2 Python (rename, docstring synthesis, "
                "type annotations). Without GnuCOBOL installed on this host the LLM "
                "judge is the only path to verdict=PASS — Stage 3 substantially "
                "raises judge scores, so default ON when a provider key is set."
            ),
        )

                                                                    
    auto_rescue = st.toggle(
        "Auto-rescue invalid Stage 2 with LLM",
        value=True,
        help="When the rule-based templater produces syntactically invalid Python, "
        "send it to the LLM to reimplement cleanly. Runs independently of Stage 3.",
    )

                                                                        
    checkpoint = load_latest()
    use_neural = False
    if checkpoint is not None:
        from pathlib import Path as _Path
        ckpt_exists = _Path(checkpoint.path).exists()
        if ckpt_exists:
            use_neural = st.toggle(
                "Use fine-tuned Stage-2 model",
                value=True,
                help=(
                    f"Replace the rule-based templater with the fine-tuned checkpoint "
                    f"at `{checkpoint.path}` (trained on {checkpoint.dataset}, "
                    f"{checkpoint.train_examples} programs, {checkpoint.epochs} epochs). "
                    "Falls back to rule-based per program if generation fails."
                ),
            )
        else:
            st.warning(
                f"Latest checkpoint pointer references `{checkpoint.path}` "
                "which is missing on disk. Re-run training or delete "
                "artifacts/checkpoints/latest.json."
            )
    else:
        st.caption(
            "No fine-tuned Stage-2 checkpoint registered yet. "
            "Train one from the Datasets → Train tab to enable the neural Stage 2."
        )

    provider = "openai"
    if run_stage3 or auto_rescue:
        provider = st.selectbox("LLM provider", options=["openai", "anthropic"])
        provider_ok = _provider_available(provider)
        st.markdown(
            badge("Available", "success") if provider_ok else badge("Key missing — LLM steps will skip", "warning"),
            unsafe_allow_html=True,
        )

                                                                        
    import shutil as _shutil
    cobc_available = _shutil.which("cobc") is not None
    judge_available = _provider_available(provider) if (run_stage3 or auto_rescue) else (
        _provider_available("openai") or _provider_available("anthropic")
    )

    bc_cols = st.columns(2)
    with bc_cols[0]:
        run_execution = st.toggle(
            "Execution match (compile COBOL with GnuCOBOL, compare stdout)",
            value=cobc_available,
            disabled=not cobc_available,
            help=(
                "Behavioural signal — passes when `cobc` compiles the COBOL "
                "and Python and stdout matches. Required for verdict=PASS unless "
                "the LLM judge runs. `brew install gnu-cobol` to enable."
                if not cobc_available
                else "Behavioural signal — required (with LLM judge) for any verdict=PASS."
            ),
        )
    with bc_cols[1]:
        run_llm_judge = st.toggle(
            "LLM judge (5-dimension rubric)",
            value=judge_available,
            disabled=not judge_available,
            help=(
                "Semantic signal — GPT-4 / Claude scores correctness, readability, "
                "PEP-8, idioms, type hints. Set OPENAI_API_KEY or ANTHROPIC_API_KEY "
                "in .env to enable."
                if not judge_available
                else "Semantic signal — flips verdict to PASS when weighted score ≥ 0.70."
            ),
        )

                                                                       
    if not (run_execution or run_llm_judge):
        st.warning(
            "No behavioural signal selected. Verdicts will be capped at "
            "**INCONCLUSIVE** even if the translation is correct — the "
            "verifier requires either execution_match or llm_judge to "
            "return PASS. Install GnuCOBOL (`brew install gnu-cobol`) "
            "or set an LLM API key in `.env` to enable a signal."
        )

    run_clicked = st.button(
        f"Transpile {max_records} program(s) →",
        type="primary",
        width="stretch",
    )
    if not run_clicked:
        st.caption("Configure above and press Transpile. Each program will show its AST, Stage 2 output, and (if enabled) Stage 3 refined Python.")
        return

                                                                        
    spec = registry.get(dataset_key)
    loader = ALL_LOADERS[dataset_key](spec)
    parser = CobolParser()
    scorer = ComplexityScorer()
    translator = RuleBasedTranslator()
    refiner = LLMRefiner(provider=provider) if run_stage3 else None
    rescue_name = provider if auto_rescue and _provider_available(provider) else None

                                                                        
    neural: NeuralTranslator | None = None
    if use_neural and checkpoint is not None:
        try:
            neural = NeuralTranslator(
                model_name=checkpoint.backbone,
                checkpoint_dir=checkpoint.path,
                device="auto",                                           
                fallback_to_rules=True,
            )
            with st.spinner("Loading fine-tuned Stage-2 model..."):
                neural.load()
        except Exception as exc:                
            st.warning(
                f"Could not load checkpoint {checkpoint.path}: {exc}. "
                "Continuing with rule-based Stage 2."
            )
            neural = None

    progress = st.progress(0.0, text="Starting...")
    results: list[dict] = []
    t0 = time.perf_counter()

    try:
        for idx, rec in enumerate(loader.iter_records(), start=1):
            if idx > max_records:
                break
            results.append(
                _process_record(
                    rec, parser, scorer, translator, refiner,
                    rescue_provider_name=rescue_name,
                    neural=neural,
                    run_execution=run_execution,
                    run_llm_judge=run_llm_judge,
                    judge_provider=_provider_chain(provider) or provider,
                )
            )
            progress.progress(min(idx / max_records, 1.0), text=f"Processed {idx} of {max_records}")
    except Exception as exc:                
        progress.empty()
        st.error(f"Batch failed: {exc}")
        return

    elapsed = time.perf_counter() - t0
    progress.empty()

    if not results:
        st.warning("No records processed.")
        return

                                                                        
    df = pd.DataFrame(
        [
            {
                "id": r["id"],
                "program_id": r["program_id"] if r["ok"] else None,
                "tier": r["tier"],
                "complexity": r["complexity"],
                "ok": r["ok"],
            }
            for r in results
        ]
    )

    st.markdown("##### Summary")
    verdicts = [r.get("verdict", "INCONCLUSIVE") for r in results]
    n_pass = sum(1 for v in verdicts if v == "PASS")
    n_fail = sum(1 for v in verdicts if v == "FAIL")
    n_incon = sum(1 for v in verdicts if v == "INCONCLUSIVE")

    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Records", f"{len(df):,}")
    s2.metric("Parse success", f"{df['ok'].mean() * 100:.0f}%")
    parsed = df[df["ok"]]
    s3.metric("Mean complexity", f"{parsed['complexity'].mean():.1f}" if not parsed.empty else "—")
    s4.metric("Verdicts", f"{n_pass}P / {n_fail}F", f"{n_incon} inconclusive")
    s5.metric("Elapsed", f"{elapsed:.1f} s")

    if not parsed.empty:
        tier_counts = (
            parsed["tier"]
            .value_counts()
            .rename_axis("tier")
            .reset_index(name="count")
            .sort_values("tier")
        )
        st.bar_chart(tier_counts, x="tier", y="count", height=220, width="stretch")

                                                                        
    st.markdown("##### Programs")
    st.caption(
        "Each card expands to show source ↔ AST tree side by side, with collapsible "
        "Stage 2 (rule-based Python) and Stage 3 (refined Python) sections below."
    )
    for idx, row in enumerate(results):
        _render_card(row, run_stage3=run_stage3, idx=idx)

                                                                        
    ensure_dir(RUNS_DIR)
    trace_paths: list[Path] = []
    for r in results:
        try:
            trace = build_trace_from_row(r)
            p = write_trace(trace)
            trace_paths.append(p)
        except Exception as exc:                
            st.warning(f"Trace write skipped for {r.get('id')}: {exc}")
    if trace_paths:
        st.caption(
            f"Wrote {len(trace_paths)} stage trace(s) to "
            f"`{RUNS_DIR.relative_to(ROOT)}/` — open any .json for full Stage 1/2/3 audit."
        )

    ensure_dir(OUTPUTS_DIR)
    out_path = OUTPUTS_DIR / f"batch_{dataset_key}_{int(time.time())}.json"
                                                                                          
    write_json(
        out_path,
        {
            "dataset": dataset_key,
            "ran_stage3": run_stage3,
            "elapsed_seconds": elapsed,
            "summary": {
                "count": int(len(df)),
                "parse_success_rate": float(df["ok"].mean()),
                "tier_distribution": parsed["tier"].value_counts().to_dict() if not parsed.empty else {},
            },
            "records": [
                {
                    "id": r["id"],
                    "program_id": r["program_id"] if r["ok"] else None,
                    "tier": r["tier"],
                    "complexity": r["complexity"],
                    "ok": r["ok"],
                    "semantic_label": r["semantic_label"],
                }
                for r in results
            ],
        },
    )
    st.caption(f"Saved batch summary to `{out_path.relative_to(ROOT)}`")


main()
