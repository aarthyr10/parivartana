
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import time
import traceback
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except Exception:                
    pass

from src.data.loaders import ALL_LOADERS
from src.data.registry import DatasetRegistry
from src.evaluation.verifier import verify
from src.pipeline.stage1_parser import CobolParser, ComplexityScorer
from src.pipeline.stage1_parser.cobc_preflight import cobc_preflight, is_cobc_available
from src.pipeline.stage1_parser.normaliser import normalise_cobol
from src.pipeline.stage2_neural.rule_based import RuleBasedTranslator
from src.pipeline.stage2_neural.translator import NeuralTranslator
from src.pipeline.stage1_parser.complexity import ComplexityTier
from src.pipeline.stage3_llm.providers import (
    AnthropicProvider,
    OpenAIProvider,
)
from src.pipeline.stage3_llm.refiner import LLMRefiner
from src.evaluation.stage_trace import StageTrace, ast_to_dict, todo_count, write_trace
from src.utils.paths import RUNS_DIR, ensure_dir


_LOCAL_PROVIDERS = {"ollama", "vllm", "local"}


def _provider_available(name: str) -> bool:
    if name == "openai":
        return OpenAIProvider().is_available()
    if name == "anthropic":
        return AnthropicProvider().is_available()
    if name in _LOCAL_PROVIDERS:
        from src.pipeline.stage3_llm.providers import get_provider as _gp
        return _gp(name).is_available()
    return False


def _provider_chain(preferred: str) -> list[str]:
    chain: list[str] = []
    if _provider_available(preferred):
        chain.append(preferred)
    if preferred in _LOCAL_PROVIDERS:
        return chain or [preferred]
    for alt in ("openai", "anthropic"):
        if alt != preferred and _provider_available(alt) and alt not in chain:
            chain.append(alt)
    return chain


class TeeLogger:

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self._fh = log_path.open("a", encoding="utf-8")

    def __call__(self, msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        self._fh.write(line + "\n")
        self._fh.flush()

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:                
            pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", default="nist_cobol", choices=list(ALL_LOADERS.keys()))
    p.add_argument("--max", type=int, default=500, help="max records to process")
    p.add_argument(
        "--stage2",
        default="rule",
        choices=["neural", "rule"],
        help=(
            "Stage 2 translator. DEFAULT 'rule' = rule-based translator "
            "(the validated path). 'neural' runs the CodeT5+ NeuralTranslator "
            "and is ONLY useful with a fine-tuned checkpoint; without one it "
            "would load the untrained base model, which produces unusable "
            "output. When --stage2 neural is requested but no checkpoint is "
            "present, we fall back to rule-based rather than the base model."
        ),
    )
    p.add_argument(
        "--checkpoint-dir",
        default="artifacts/checkpoints/codet5p_cobol",
        help="fine-tuned CodeT5+ checkpoint dir for --stage2 neural (falls back to the base HF model, then to rules).",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=1,
        help=(
            "FAST MODE. Number of threads used to pre-warm the LLM-judge cache "
            "concurrently before the main pass (default 1 = sequential, "
            "unchanged behaviour). With e.g. --workers 8 the hundreds of judge "
            "calls run in parallel and the main pass then hits the cache, "
            "cutting a judged run from many minutes to a fraction. Applies to "
            "judged runs without --stage3 (Stage-3 output is non-deterministic "
            "so its judge calls can't be pre-cached)."
        ),
    )
    p.add_argument(
        "--entry-fallthrough",
        action="store_true",
        help=(
            "OPT-IN (default off; v12 behaviour unchanged when off). Make the "
            "entrypoint call all paragraphs in source order (COBOL fall-through) "
            "instead of only the picked main paragraph. Helps programs whose "
            "control paragraph is empty, but may double-run PERFORMed paragraphs. "
            "Validate on the LLM judge before adopting."
        ),
    )
    p.add_argument(
        "--pythonic",
        action="store_true",
        help=(
            "OPT-IN (default off; v12 behaviour unchanged when off). Emit more "
            "idiomatic Python where safe (e.g. DISPLAY uses print(..., sep='') to "
            "match COBOL concatenation). Validate on the LLM judge before adopting."
        ),
    )
    p.add_argument(
        "--judge",
        default="openai",
        choices=["openai", "anthropic", "ollama", "vllm", "local", "none"],
        help=(
            "provider for the llm_judge check. 'ollama'/'vllm'/'local' use a "
            "local OpenAI-compatible server (free, no API cost) — set "
            "--judge-model to your local model (e.g. llama3.1:8b). openai/"
            "anthropic build a paid fallback chain; local providers never "
            "fall back to paid APIs."
        ),
    )
    p.add_argument(
        "--stage3",
        action="store_true",
        help="run Stage 3 LLM refinement before scoring (slower)",
    )
    p.add_argument(
        "--judge-model",
        default="gpt-4o-mini",
        help=(
            "model used by the LLM judge. DEFAULT gpt-4o-mini — ~30x cheaper "
            "and far faster than the full gpt-4o, which matters when judging "
            "hundreds of programs. Pass a larger model explicitly if needed."
        ),
    )
    p.add_argument(
        "--stage3-min-tier",
        default="simple",
        choices=["simple", "medium", "high"],
        help=(
            "minimum complexity tier that gets Stage 3 LLM refinement. "
            "Default 'simple' = refine everything (matches previous behaviour). "
            "Set to 'medium' to skip the ~112/500 simple-tier programs and "
            "save ~25%% of LLM spend; their rule-based output is usually "
            "clean enough that the LLM rewrite is wasted money."
        ),
    )
                                          
    p.add_argument(
        "--cobc-preflight",
        action="store_true",
        help=(
            "run `cobc -fsyntax-only` on each program before our parser. "
            "Separates 'COBOL is broken' from 'our parser failed to handle it'. "
            "Requires GnuCOBOL on PATH (brew install gnucobol)."
        ),
    )
                                       
                                                                         
    p.add_argument(
        "--normalise",
        dest="normalise",
        action="store_true",
        default=True,
        help=(
            "(DEFAULT ON since v11) apply the Stage 1 regex normaliser "
            "before parsing (strips fixed-format margins, decodes intrinsic "
            "functions, marks AT END/INVALID KEY, expands INSPECT, marks "
            "OCCURS). Estimated 1,500-2,500 paragraphs un-stubbed on NIST."
        ),
    )
    p.add_argument(
        "--no-normalise",
        dest="normalise",
        action="store_false",
        help="opt out of the Stage 1 regex normaliser (pre-v11 behaviour).",
    )
                                                
    p.add_argument(
        "--legacylens-diff",
        action="store_true",
        help=(
            "run cobol_parser as a second opinion and diff CALLs/PERFORMs "
            "against our AST. Read-only quality metric; logs to patterns.json."
        ),
    )
                                       
    p.add_argument(
        "--proleap-fallback",
        action="store_true",
        help=(
            "use ProLeap (Java) to re-check paragraphs our parser stubbed. "
            "Requires jpype1 and the proleap-cobol-parser jar. "
            "See src/pipeline/stage1_parser/proleap_fallback.py for setup."
        ),
    )
                                                                         
                                                                            
    p.add_argument(
        "--exclude-fragments",
        dest="exclude_fragments",
        action="store_true",
        default=True,
        help=(
            "(DEFAULT ON since v11) skip files that don't look like complete "
            "COBOL programs (no IDENTIFICATION DIVISION / PROGRAM-ID). Removes "
            "copybook fragments whose inclusion inflates counts without "
            "measuring translation quality."
        ),
    )
    p.add_argument(
        "--include-fragments",
        dest="exclude_fragments",
        action="store_false",
        help="include copybook fragments in scoring (pre-v11 behaviour).",
    )
                                     
    p.add_argument(
        "--no-python-smoke",
        action="store_true",
        help=(
            "skip the Python-smoke check (subprocess-runs the translated "
            "Python and confirms no crash). On by default; this is the "
            "biggest deterministic lever for moving STRUCTURAL_PASS to "
            "actual PASS without needing cobc or an LLM API."
        ),
    )
                                   
    p.add_argument(
        "--llm-rescue",
        action="store_true",
        help=(
            "after a program FAILs the verifier, fire one more LLM call "
            "asking the model to rewrite the Python given the failing "
            "checks. Re-runs the structural checks on the rescued "
            "version; if it passes, the verdict becomes PASS. Costs one "
            "extra LLM call per FAIL (~$0.001/program on gpt-4o-mini). "
            "No-op when no provider key is set."
        ),
    )
    p.add_argument(
        "--llm-promote",
        action="store_true",
        help=(
            "for programs landing at STRUCTURAL_PASS (structure clean, "
            "behavioural signal unavailable), ask the LLM a single "
            "yes/no question — 'is this Python a faithful translation?' "
            "— and promote to PASS when the model says YES. ~20x cheaper "
            "than the rubric judge (one-word answers). Roughly $0.0008 "
            "per call on gpt-4o-mini. Useful when execution_match can't "
            "run (no cobc, file-I/O sandbox limitation) and the full "
            "rubric judge is over budget."
        ),
    )
    p.add_argument(
        "--run-id",
        default=f"cli_{int(time.time())}",
        help="folder name under artifacts/runs/ for this run's outputs",
    )
    p.add_argument(
        "--order",
        default="complexity",
        choices=["complexity", "as-loaded"],
        help="program ordering for the second pass",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if args.judge in _LOCAL_PROVIDERS and (args.judge_model or "").lower().startswith("gpt"):
        args.judge_model = None

    out_dir = ensure_dir(RUNS_DIR / args.run_id)
    for _stale in out_dir.glob("*__*.json"):
        try:
            _stale.unlink()
        except OSError:
            pass
    log = TeeLogger(out_dir / "run.log")
    log(f"Batch run starting: dataset={args.dataset} max={args.max} judge={args.judge} stage3={args.stage3} run_id={args.run_id}")
    log(
        f"Audit-driven passes: cobc_preflight={args.cobc_preflight} "
        f"normalise={args.normalise} legacylens={args.legacylens_diff} "
        f"proleap={args.proleap_fallback}"
    )

                                                                          
    if args.judge == "none":
        judge_providers: list[str] = []
        run_llm_judge = False
    else:
        judge_providers = _provider_chain(args.judge)
                                                                  
                                                                
        run_llm_judge = True
        if not judge_providers:
                                                                     
                                                            
            judge_providers = [args.judge] + (
                ["openai", "anthropic"]
                if args.judge not in {"openai", "anthropic"}
                else [p for p in ("openai", "anthropic") if p != args.judge]
            )
            log(
                f"INFO: no provider keys set; behavioural judge will skip "
                f"(STRUCTURAL_PASS will fire when structure is clean)"
            )
    cobc_available = shutil.which("cobc") is not None
    log(f"Provider chain for llm_judge: {judge_providers or 'NONE'}; cobc on PATH: {cobc_available}")

                                                                          
    registry = DatasetRegistry()
    try:
        spec = registry.get(args.dataset)
    except Exception as exc:                
        log(f"FATAL: dataset {args.dataset!r} not found in registry: {exc}")
        return 2
    loader = ALL_LOADERS[args.dataset](spec)
    if not loader.is_available():
        log(f"FATAL: dataset {args.dataset!r} not present at {spec.local_path}")
        return 2

    parser = CobolParser()
    scorer = ComplexityScorer()
    rule_translator = RuleBasedTranslator()
    if args.stage2 == "neural" and not Path(args.checkpoint_dir).exists():
        neural_translator = None
        log(
            f"Stage 2: --stage2 neural requested but no fine-tuned checkpoint at "
            f"{args.checkpoint_dir!r}; the untrained base model produces unusable "
            f"output, so using the rule-based translator instead."
        )
    elif args.stage2 == "neural":
        neural_translator = NeuralTranslator(
            checkpoint_dir=args.checkpoint_dir,
            fallback_to_rules=True,
        )
        try:
            neural_translator.load()
            log(f"Stage 2: NeuralTranslator loaded ({neural_translator.model_name}).")
        except Exception as exc:
                                                                            
                                                                         
            neural_translator = None
            log(
                f"Stage 2: NeuralTranslator unavailable ({type(exc).__name__}); "
                f"using rule-based translator for this run."
            )
    else:
        neural_translator = None
        log("Stage 2: rule-based translator (forced via --stage2 rule).")
    refiner = (
        LLMRefiner(provider=judge_providers[0] if judge_providers else "openai")
        if args.stage3 and judge_providers
        else None
    )
    if args.stage3 and not judge_providers:
        log("Stage 3 was requested but no provider key is set — running Stages 1+2 only.")

                                                                          
    log("Pass 1: parsing + complexity scoring...")
    records: list[dict[str, Any]] = []
    fragments_skipped = 0
    t_pass1 = time.perf_counter()
    for idx, rec in enumerate(loader.iter_records(), start=1):
        if idx > max(args.max * 3, args.max):
                                                                     
                                                                      
            break
                                                                 
        if args.exclude_fragments and rec.get("is_complete_program") is False:
            fragments_skipped += 1
            continue
        source_raw = rec.get("source") or rec.get("content") or ""
                                                                      
                                                                 
        norm_imports: set[str] = set()
        if args.normalise:
            norm = normalise_cobol(source_raw)
            source = norm.cobol
            norm_imports = norm.needed_imports
        else:
            source = source_raw
        try:
            parse = parser.parse(source)
        except Exception as exc:                
            records.append({"rec": rec, "parse_ok": False, "complexity": float("inf"), "parse_err": str(exc), "score": None, "parse": None, "source_raw": source_raw, "norm_imports": norm_imports})
            continue
        if not parse.ok or parse.ast is None:
            records.append({"rec": rec, "parse_ok": False, "complexity": float("inf"), "parse_err": "stage1 parse failed", "score": None, "parse": parse, "source_raw": source_raw, "norm_imports": norm_imports})
            continue
        try:
            score = scorer.score(parse.ast)
            complexity = score.raw_score
        except Exception:                
            complexity = float("inf")
            score = None
        records.append({"rec": rec, "parse_ok": True, "complexity": complexity, "parse_err": "", "score": score, "parse": parse, "source_raw": source_raw, "norm_imports": norm_imports})
        if idx % 200 == 0:
            log(f"  parsed {idx} ...")
    log(
        f"Pass 1 done: {len(records)} records in {time.perf_counter() - t_pass1:.1f}s"
        + (f" (skipped {fragments_skipped} copybook fragment(s))" if fragments_skipped else "")
    )

                                                                          
    if args.order == "complexity":
                                                                         
                                                        
        records.sort(key=lambda r: (not r["parse_ok"], r["complexity"]))
    records = records[: args.max]
    log(f"Pass 2: processing top {len(records)} records (order={args.order})")

    if args.workers > 1 and run_llm_judge and judge_providers and refiner is None:
        import concurrent.futures as _cf

        def _warm(item: dict[str, Any]) -> None:
            if not item.get("parse_ok") or item.get("parse") is None:
                return
            try:
                rec_w = item["rec"]
                src_w = rec_w.get("source") or rec_w.get("content") or ""
                code_w = rule_translator.translate(
                    item["parse"].ast,
                    options={
                        "entry_fallthrough": args.entry_fallthrough,
                        "pythonic": args.pythonic,
                    },
                ).code
                if item.get("norm_imports"):
                    imps = "\n".join(f"import {m}" for m in sorted(item["norm_imports"]))
                    code_w = f"{imps}\n\n{code_w}"
                verify(
                    cobol_source=src_w,
                    python_source=code_w,
                    ast=item["parse"].ast,
                    run_execution=False,
                    run_llm_judge=True,
                    run_python_smoke=False,
                    run_llm_rescue=False,
                    run_llm_promote=False,
                    llm_provider=judge_providers,
                    llm_model=args.judge_model,
                )
            except Exception:
                pass

        log(f"Pre-warming judge cache with {args.workers} workers (fast mode)...")
        t_warm = time.perf_counter()
        try:
            with _cf.ThreadPoolExecutor(max_workers=args.workers) as _ex:
                list(_ex.map(_warm, records))
            log(f"Pre-warm done in {time.perf_counter() - t_warm:.1f}s; main pass will hit the cache.")
        except Exception as exc:
            log(f"Pre-warm skipped ({type(exc).__name__}); falling back to sequential judging.")

                                                                           
    summary_csv = (out_dir / "summary.csv").open("w", newline="", encoding="utf-8")
    progress_csv = (out_dir / "progress.csv").open("w", newline="", encoding="utf-8")
    summary_writer = csv.writer(summary_csv)
    progress_writer = csv.writer(progress_csv)
    summary_writer.writerow([
        "idx", "program_id", "record_id", "tier", "complexity",
        "stage1_ok", "stage2_source", "stage3_ran",
        "verdict", "verdict_summary",
        "syntax_ok", "paragraph_score", "identifier_score",
        "judge_ran", "judge_score", "judge_detail",
    ])
    progress_writer.writerow(["idx", "pass", "fail", "inconclusive", "stage1_fail", "pass_pct", "fail_pct", "inconclusive_pct"])

    tally: Counter[str] = Counter()
    pattern_buckets: dict[str, Counter[str]] = defaultdict(Counter)
    judge_weighted: list[float] = []
    judge_correctness: list[float] = []

    t_pass2 = time.perf_counter()
    for idx, item in enumerate(records, start=1):
        rec = item["rec"]
        parse = item["parse"]
        score = item["score"]
        source = rec.get("source") or rec.get("content") or ""
        source_raw = item.get("source_raw", source)
        record_id = rec.get("id") or rec.get("instance_id") or f"row_{idx}"

        trace = StageTrace(
            program_id=str(rec.get("id") or record_id),
            record_id=str(record_id),
            cobol_source=source_raw,                                        
        )

                                                                     
        if args.cobc_preflight:
            pre = cobc_preflight(source_raw)
            trace.stage1_cobc_status = pre.status
            trace.stage1_cobc_stderr = pre.stderr[:1000]
            pattern_buckets["stage1_cobc_status"][pre.status] += 1
            if pre.status == "rejected" and item.get("parse_ok"):
                                                                       
                                                                    
                pattern_buckets["our_parser_accepted_cobc_rejected"][record_id[:60]] += 1
            elif pre.status == "accepted" and not item.get("parse_ok"):
                                                                        
                                                                
                pattern_buckets["our_parser_failed_cobc_accepted"][record_id[:60]] += 1

                                     
        if not item["parse_ok"]:
            trace.stage1_ok = False
            trace.stage1_errors = [item.get("parse_err") or "stage1 parse failed"]
            trace.verdict = "FAIL"
            trace.verdict_summary = "Stage 1 parse failed"
            tally["FAIL"] += 1
            tally["stage1_fail"] += 1
            pattern_buckets["stage1_fail_reason"][item.get("parse_err") or "unknown"] += 1
            _write_outputs(trace, out_dir, summary_writer, idx, score)
            _emit_progress(progress_writer, idx, tally)
            continue

        trace.stage1_ok = True
        trace.stage1_program_id = parse.program_id or ""
        trace.stage1_division_count = parse.division_count
        trace.stage1_paragraph_count = parse.paragraph_count
        trace.stage1_token_count = len(parse.tokens)
        trace.stage1_ast = ast_to_dict(parse.ast)
        trace.stage1_warnings = list(parse.warnings or [])
        if score is not None:
            trace.complexity_tier = score.tier.value
            trace.complexity_score = float(score.raw_score)
            trace.ast_depth = int(score.ast_depth)
            trace.unique_verbs = int(score.unique_verb_count)
            trace.cross_refs = int(score.cross_ref_count)

                           
        tier = score.tier if score is not None else ComplexityTier.MEDIUM
        if neural_translator is not None:
            tr_res = neural_translator.translate(parse.ast, tier)
            stage2_python = tr_res.python_code
            used_fallback = bool(tr_res.metadata.get("fallback"))
            trace.stage2_source = "rule-based-fallback" if used_fallback else "neural"
            stage2_warnings = list(tr_res.metadata.get("warnings", []) or [])
            pattern_buckets["stage2_translator"][
                "rule-based-fallback" if used_fallback else f"neural:{tr_res.model_name}"
            ] += 1
        else:
            rb = rule_translator.translate(
                parse.ast,
                options={
                    "entry_fallthrough": args.entry_fallthrough,
                    "pythonic": args.pythonic,
                },
            )
            stage2_python = rb.code
            trace.stage2_source = "rule-based"
            stage2_warnings = list(rb.warnings or [])
            pattern_buckets["stage2_translator"]["rule-based"] += 1
                                                                
                                                      
        if item.get("norm_imports"):
            import_lines = "\n".join(f"import {m}" for m in sorted(item["norm_imports"]))
            stage2_python = f"{import_lines}\n\n{stage2_python}"
        trace.stage2_rule_based_code = stage2_python
        trace.stage2_final_code = stage2_python
        trace.stage2_warnings = stage2_warnings
        trace.stage2_todo_count = todo_count(stage2_python)

                                                                      
        if args.legacylens_diff:
            from src.evaluation.legacylens_diff import coverage_diff

            diff = coverage_diff(source_raw, parse.ast)
            if diff.available:
                for name in diff.missed_calls:
                    pattern_buckets["missed_call"][name[:60]] += 1
                for name in diff.missed_performs:
                    pattern_buckets["missed_perform"][name[:60]] += 1
                for name in diff.missed_io_files:
                    pattern_buckets["missed_io_file"][name[:60]] += 1

                                                                        
        if args.proleap_fallback:
            from src.pipeline.stage1_parser.proleap_fallback import coverage_vs_ours

            pl = coverage_vs_ours(source_raw, parse.ast)
            if pl.get("proleap_available"):
                for name in (pl.get("missed_by_us") or [])[:5]:
                    pattern_buckets["proleap_extra_paragraphs"][name[:60]] += 1
            else:
                pattern_buckets["proleap_unavailable"][pl.get("reason","unknown")[:60]] += 1

                           
        refined_python = ""
                                                                    
                                                                         
        tier_rank = {"simple": 0, "medium": 1, "high": 2}
        tier_str = score.tier.value if score else "simple"
        stage3_gated_out = (
            refiner is not None
            and tier_rank.get(tier_str, 0) < tier_rank.get(args.stage3_min_tier, 0)
        )
        if stage3_gated_out:
            pattern_buckets["stage3_skipped"][f"tier={tier_str} below {args.stage3_min_tier}"] += 1
        if refiner is not None and not stage3_gated_out:
            try:
                identifiers = sorted(
                    {
                        n.attributes["name"]
                        for n in parse.ast.walk()
                        if n.node_type == "DataItem" and "name" in n.attributes
                    }
                )
                result = refiner.refine(
                    raw_python=stage2_python,
                    tier=score.tier if score else None,
                    cobol_identifiers=identifiers,
                    cobol_comment="",
                    run_semantic_check=False,
                    run_docstring_synthesis=False,
                    cobol_source=source,
                )
                refined_python = result.refined_python or ""
                trace.stage3_ran = bool(refined_python)
                trace.stage3_refined_code = refined_python
                                                                         
                                                                      
                renamed = result.metadata.get("renamed_identifiers", []) if isinstance(getattr(result, "metadata", None), dict) else []
                trace.stage3_rename_map = {n: n for n in renamed}                   
                trace.stage3_docstrings_added = int(
                    result.metadata.get("docstrings_added", 0)
                    if isinstance(getattr(result, "metadata", None), dict)
                    else 0
                )
                trace.stage3_provider = getattr(result, "provider", "") or (
                    judge_providers[0] if judge_providers else ""
                )
                if getattr(result, "semantic_check", None):
                    trace.stage3_semantic_label = result.semantic_check.label.value
                                                                    
                                                                
                if isinstance(getattr(result, "metadata", None), dict) and result.metadata.get("llm_truncated"):
                    pattern_buckets["stage3_llm_truncated"]["max_tokens hit"] += 1
            except Exception as exc:                
                trace.stage3_error = str(exc)[:240]
                pattern_buckets["stage3_error"][type(exc).__name__] += 1

                          
        eval_target = refined_python or stage2_python
        try:
            report = verify(
                cobol_source=source,
                python_source=eval_target,
                ast=parse.ast,
                run_execution=cobc_available,
                run_llm_judge=run_llm_judge,
                run_python_smoke=not args.no_python_smoke,
                run_llm_rescue=args.llm_rescue and bool(judge_providers),
                run_llm_promote=args.llm_promote and bool(judge_providers),
                llm_provider=judge_providers or "openai",
                llm_model=args.judge_model,
            )
            trace.verdict = report.verdict
            trace.verdict_summary = report.summary
            trace.verdict_checks = [
                {
                    "name": c.name,
                    "ran": c.ran,
                    "passed": c.passed,
                    "score": c.score,
                    "detail": c.detail,
                    "skipped_reason": c.skipped_reason,
                                                                         
                                                                 
                    "extra": c.extra,
                }
                for c in report.checks
            ]
                                                                  
                                                                
            rescue_check = next(
                (c for c in report.checks if c.name == "llm_rescue"), None
            )
            if rescue_check and rescue_check.ran and rescue_check.passed:
                ex = rescue_check.extra or {}
                pattern_buckets["llm_rescued"][
                    f"{','.join(ex.get('original_failed_checks', []))[:60]} via {ex.get('provider','?')}"
                ] += 1
                                                                   
            jcheck = next(
                (c for c in report.checks if c.name == "llm_judge"), None
            )
            if jcheck and jcheck.ran:
                if jcheck.score is not None:
                    judge_weighted.append(float(jcheck.score))
                _comp = (jcheck.extra or {}).get("components") or {}
                if "correctness" in _comp:
                    judge_correctness.append(float(_comp["correctness"]))
            promote_check = next(
                (c for c in report.checks if c.name == "llm_promote"), None
            )
            if promote_check:
                ex = promote_check.extra or {}
                if promote_check.passed:
                    pattern_buckets["llm_promoted"][f"via {ex.get('provider','?')}"] += 1
                elif promote_check.passed is False:
                    pattern_buckets["llm_promote_rejected"][
                        ex.get("attempts", ["?"])[-1][:60]
                    ] += 1
                else:
                    pattern_buckets["llm_promote_unavailable"][
                        (ex.get("attempts") or ["?"])[-1][:60]
                    ] += 1
                                                                                     
            judge_check = report.get("llm_judge")
            if (
                trace.verdict == "INCONCLUSIVE"
                and judge_check is not None
                and not judge_check.ran
                and judge_check.skipped_reason
            ):
                trace.verdict_summary = (
                    f"{trace.verdict_summary} llm_judge skipped: {judge_check.skipped_reason}"
                )
                pattern_buckets["judge_skipped_reason"][judge_check.skipped_reason[:80]] += 1
                                         
            for c in report.checks:
                if c.ran and c.passed is False:
                    pattern_buckets[f"failed_{c.name}"][(c.detail or "")[:80]] += 1
        except Exception as exc:                
            trace.verdict = "INCONCLUSIVE"
            trace.verdict_summary = f"verifier crashed: {exc}"
            pattern_buckets["verifier_crash"][type(exc).__name__] += 1

        tally[trace.verdict] += 1
        _write_outputs(trace, out_dir, summary_writer, idx, score)
        _emit_progress(progress_writer, idx, tally)

        if idx % 25 == 0 or idx == len(records):
            log(
                f"  [{idx:4d}/{len(records)}] "
                f"PASS={tally['PASS']} FAIL={tally['FAIL']} INC={tally['INCONCLUSIVE']} "
                f"S1FAIL={tally['stage1_fail']}"
            )

    summary_csv.close()
    progress_csv.close()

                                                                          
    total = sum(
        tally[k] for k in ("PASS", "STRUCTURAL_PASS", "FAIL", "INCONCLUSIVE")
    )
    pct = lambda k: (100.0 * tally[k] / total) if total else 0.0
                                                                        
                                                                   
    headline_pass = tally["PASS"] + tally["STRUCTURAL_PASS"]
    headline_pct = (100.0 * headline_pass / total) if total else 0.0
    log("=" * 60)
    log(f"Run complete in {time.perf_counter() - t_pass2:.1f}s")
    log(f"Total scored: {total}")
    log(f"  HEADLINE PASS:    {headline_pass:5d}  ({headline_pct:.1f}%)")
    log(f"    PASS (behav.):  {tally['PASS']:5d}  ({pct('PASS'):.1f}%)")
    log(f"    STRUCTURAL:     {tally['STRUCTURAL_PASS']:5d}  ({pct('STRUCTURAL_PASS'):.1f}%)")
    log(f"  FAIL:             {tally['FAIL']:5d}  ({pct('FAIL'):.1f}%)")
    log(f"  INCONCLUSIVE:     {tally['INCONCLUSIVE']:5d}  ({pct('INCONCLUSIVE'):.1f}%)")
    log(f"  Stage 1 fails: {tally['stage1_fail']}")
    judge_mean = (sum(judge_weighted) / len(judge_weighted)) if judge_weighted else None
    corr_mean = (sum(judge_correctness) / len(judge_correctness)) if judge_correctness else None
    if judge_weighted:
        log(
            f"  LLM-judge (n={len(judge_weighted)}): mean weighted={judge_mean:.3f}, "
            f"mean correctness={corr_mean:.3f}"
            + (f", mean correctness=n/a" if corr_mean is None else "")
        )

    patterns_out: dict[str, list[dict]] = {}
    for bucket, counts in pattern_buckets.items():
        patterns_out[bucket] = [
            {"reason": reason, "count": count}
            for reason, count in counts.most_common(20)
        ]
    (out_dir / "patterns.json").write_text(json.dumps(patterns_out, indent=2))
    log(f"Patterns written to {out_dir / 'patterns.json'}")

    summary_md = out_dir / "summary.md"
    with summary_md.open("w") as fh:
        fh.write(f"# Batch run {args.run_id}\n\n")
        fh.write(f"- Dataset: **{args.dataset}** (max={args.max})\n")
        fh.write(f"- Judge providers: `{judge_providers}`\n")
        fh.write(f"- Stage 3: **{args.stage3}**\n")
        fh.write(f"- **Headline PASS rate: {headline_pct:.1f}% ({headline_pass}/{total})**\n")
        if judge_weighted:
            fh.write(
                f"- **LLM-judge** (n={len(judge_weighted)}): mean weighted "
                f"**{judge_mean:.3f}**"
                + (f", mean correctness **{corr_mean:.3f}**" if corr_mean is not None else "")
                + " (use this, not the 0.70 binary, where execution_match can't run)\n"
            )
        fh.write("\n")
        fh.write("## Verdict distribution\n\n")
        fh.write(f"| Verdict | Count | % |\n|---|---:|---:|\n")
        for v in ("PASS", "STRUCTURAL_PASS", "FAIL", "INCONCLUSIVE"):
            fh.write(f"| {v} | {tally[v]} | {pct(v):.1f}% |\n")
        fh.write(f"\nStage 1 failures: {tally['stage1_fail']}\n\n")
        fh.write("## Top failure patterns\n\n")
        for bucket, items in patterns_out.items():
            fh.write(f"### `{bucket}`\n\n")
            for it in items[:10]:
                fh.write(f"- ({it['count']}) {it['reason']}\n")
            fh.write("\n")
    log(f"Summary written to {summary_md}")

    log.close()
    return 0


def _write_outputs(
    trace: StageTrace,
    out_dir: Path,
    summary_writer: "csv._writer",
    idx: int,
    score,
) -> None:
                                                                        
                                                                       
    write_trace(trace, out_dir=out_dir)
                                      
    syntax_ok = next(
        (c["passed"] for c in trace.verdict_checks if c["name"] == "python_syntax_valid"),
        None,
    )
    para_score = next(
        (c["score"] for c in trace.verdict_checks if c["name"] == "paragraph_coverage"),
        None,
    )
    ident_score = next(
        (c["score"] for c in trace.verdict_checks if c["name"] == "identifier_coverage"),
        None,
    )
    judge_check = next(
        (c for c in trace.verdict_checks if c["name"] == "llm_judge"),
        None,
    )
    summary_writer.writerow([
        idx,
        trace.program_id,
        trace.record_id,
        trace.complexity_tier,
        f"{trace.complexity_score:.2f}",
        trace.stage1_ok,
        trace.stage2_source,
        trace.stage3_ran,
        trace.verdict,
        trace.verdict_summary,
        syntax_ok,
        para_score,
        ident_score,
        judge_check["ran"] if judge_check else None,
        judge_check["score"] if judge_check else None,
        (judge_check["detail"] if judge_check else "")[:120] if judge_check else "",
    ])


def _emit_progress(writer: "csv._writer", idx: int, tally: Counter[str]) -> None:
    total = sum(tally[k] for k in ("PASS", "FAIL", "INCONCLUSIVE"))
    pct = lambda k: (100.0 * tally[k] / total) if total else 0.0
    writer.writerow([
        idx,
        tally["PASS"],
        tally["FAIL"],
        tally["INCONCLUSIVE"],
        tally["stage1_fail"],
        f"{pct('PASS'):.1f}",
        f"{pct('FAIL'):.1f}",
        f"{pct('INCONCLUSIVE'):.1f}",
    ])


if __name__ == "__main__":
    sys.exit(main())
