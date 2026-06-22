from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.loaders import ALL_LOADERS
from src.data.registry import DatasetRegistry
from src.pipeline.stage1_parser import CobolParser, ComplexityScorer
from src.pipeline.stage1_parser.normaliser import normalise_cobol
from src.pipeline.stage2_neural.prompt_builder import PromptBuilder
from src.pipeline.stage2_neural.rule_based import RuleBasedTranslator
from src.utils.logging import get_logger

log = get_logger(__name__)

_TEACHER_SYSTEM = (
    "You are an expert COBOL-to-Python engineer. Translate the COBOL program "
    "into a single self-contained Python 3 module. The Python must reproduce "
    "the program's observable behaviour exactly: same stdout, same arithmetic, "
    "same control flow. Use real local variables (not a state dict), idiomatic "
    "Python, and implement every paragraph fully with no stubs, no TODOs, and "
    "no placeholder pass bodies. Return only the Python code inside one ```python "
    "fenced block."
)

_FENCE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _extract_code(text: str) -> str:
    m = _FENCE.search(text or "")
    if m:
        return m.group(1).strip()
    return (text or "").strip()


def _llm_target(provider, cobol_source: str) -> str:
    user = "Translate this COBOL program to Python 3:\n\n" + cobol_source
    resp = provider.complete(_TEACHER_SYSTEM, user)
    return _extract_code(resp.text)


def _norm(s: str) -> str:
    return "\n".join(line.rstrip() for line in (s or "").splitlines()).strip()


def _run_cobol_once(checker, src: str):
    try:
        out, rc = checker.run_cobol(src)
        return out, rc, None
    except subprocess.TimeoutExpired:
        return "", -1, "cobol_timeout"
    except FileNotFoundError:
        return "", -1, "cobc_not_found"
    except Exception as exc:
        return "", -1, type(exc).__name__


def _gather_candidates(datasets, max_per, max_cobol_lines):
    registry = DatasetRegistry()
    parser = CobolParser()
    scorer = ComplexityScorer()
    rule = RuleBasedTranslator()
    pb = PromptBuilder()
    candidates = []
    for name in datasets:
        try:
            loader = ALL_LOADERS[name](registry.get(name))
        except Exception as exc:
            log.warning(f"skip dataset {name}: {exc}")
            continue
        if not loader.is_available():
            log.warning(f"skip dataset {name}: not available locally")
            continue
        n = 0
        for rec in loader.iter_records():
            if n >= max_per:
                break
            if rec.get("is_complete_program") is False:
                continue
            src = rec.get("source") or rec.get("content") or ""
            if not src.strip():
                continue
            if max_cobol_lines and src.count("\n") + 1 > max_cobol_lines:
                continue
            try:
                parse = parser.parse(normalise_cobol(src).cobol)
                if not parse.ok or parse.ast is None:
                    continue
                tier = scorer.score(parse.ast).tier
                prompt = pb.build(parse.ast, tier).text
                rule_target = rule.translate(parse.ast).code
            except Exception as exc:
                log.debug(f"{rec.get('id','?')}: parse/score error {type(exc).__name__}: {exc}")
                continue
            if not prompt.strip():
                continue
            candidates.append(
                {
                    "id": str(rec.get("id") or rec.get("instance_id") or f"{name}_{n}"),
                    "dataset": name,
                    "tier": tier.value,
                    "prompt": prompt,
                    "cobol": src,
                    "rule_target": rule_target,
                }
            )
            n += 1
        log.info(f"dataset {name}: {n} parseable candidates")
    return candidates


def _emit(item, target, targets, verified):
    return "keep", {
        "source_prompt": item["prompt"],
        "target_python": target,
        "tier": item["tier"],
        "source_id": item["id"],
        "target_source": targets,
        "verified": verified,
    }


def _process_one(item, provider, checker, targets, keep_unverified):
    cobol_out = None
    cobol_ok = True
    if checker is not None:
        out, rc, err = _run_cobol_once(checker, item["cobol"])
        if err is not None or rc != 0:
            cobol_ok = False
        else:
            cobol_out = out
        if not cobol_ok and not keep_unverified:
            return ("skip_cobol_" + err if err else "skip_cobol_rc"), None

    if targets == "llm":
        try:
            target = _llm_target(provider, item["cobol"])
        except Exception as exc:
            return "skip_llm_" + type(exc).__name__, None
    else:
        target = item["rule_target"]
    if not target or not target.strip():
        return "skip_empty_target", None

    verified = None
    if checker is not None and cobol_ok:
        try:
            py_out, _py_rc = checker.run_python(target)
        except subprocess.TimeoutExpired:
            py_out = None
        except Exception:
            py_out = None
        if py_out is None:
            verified = False
        else:
            verified = _norm(cobol_out) == _norm(py_out)
        if not verified and not keep_unverified:
            return "skip_mismatch", None
    elif checker is not None and not cobol_ok:
        verified = False

    return _emit(item, target, targets, verified)


def _load_jsonl(path):
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    return rows


def _py_valid(code):
    try:
        compile(code, "<target>", "exec")
        return True
    except Exception:
        return False


def _postprocess(examples, require_python_valid, gold_weight):
    stats = {}
    if require_python_valid:
        before = len(examples)
        examples = [e for e in examples if _py_valid(e.get("target_python", ""))]
        stats["dropped_invalid_python"] = before - len(examples)
    if gold_weight and gold_weight > 1:
        gold = [e for e in examples if e.get("verified")]
        extra = gold * (gold_weight - 1)
        examples = examples + extra
        stats["gold_upweighted_copies"] = len(extra)
    return examples, stats


def _split_and_write(examples, out_dir, val_frac, seed, stats):
    random.Random(seed).shuffle(examples)
    n_val = int(len(examples) * val_frac)
    val, train = examples[:n_val], examples[n_val:]
    (out_dir / "train.jsonl").write_text("\n".join(json.dumps(e) for e in train))
    (out_dir / "val.jsonl").write_text("\n".join(json.dumps(e) for e in val))
    (out_dir / "build_stats.json").write_text(json.dumps(stats, indent=2))
    log.info(f"DONE: {len(train)} train / {len(val)} val -> {out_dir}")
    log.info(f"stats: {stats}")


def build(
    datasets, out_dir, max_per, val_frac, seed, targets,
    provider_name, teacher_model, execution_filter, timeout, workers,
    keep_unverified, sample, max_cobol_lines, resume, finalize,
    require_python_valid, gold_weight,
):
    out_dir.mkdir(parents=True, exist_ok=True)
    kept_path = out_dir / "kept.jsonl"
    attempted_path = out_dir / "attempted.jsonl"

    if finalize:
        examples = _load_jsonl(kept_path)
        raw = len(examples)
        gold = sum(1 for e in examples if e.get("verified"))
        examples, pp = _postprocess(examples, require_python_valid, gold_weight)
        stats = {"finalized_from": str(kept_path), "raw": raw, "gold": gold, "final": len(examples)}
        stats.update(pp)
        _split_and_write(examples, out_dir, val_frac, seed, stats)
        return

    provider = None
    if targets == "llm":
        from src.pipeline.stage3_llm.providers import get_provider

        kwargs = {"model": teacher_model} if teacher_model else {}
        provider = get_provider(provider_name, **kwargs)
        if not provider.is_available():
            raise SystemExit(
                f"teacher provider '{provider_name}' is not reachable. Set "
                "OPENAI_API_KEY / ANTHROPIC_API_KEY, or start a local server "
                "(ollama/vllm) and set LOCAL_LLM_BASE_URL."
            )
        log.info(f"teacher: provider={provider_name} model={provider.model}")

    checker = None
    if execution_filter:
        from src.evaluation.execution import ExecutionAccuracy

        checker = ExecutionAccuracy(timeout_seconds=timeout)
        if not checker.available:
            raise SystemExit(
                "execution_filter requested but GnuCOBOL (cobc) was not found. "
                "Install it or set GNUCOBOL_PATH, or drop --execution-filter."
            )
        log.info(f"execution filter ON (cobc={checker.cobol_compiler}, timeout={timeout}s)")

    log.info(f"gathering candidates from {datasets} (max_per={max_per}, max_cobol_lines={max_cobol_lines}) ...")
    candidates = _gather_candidates(datasets, max_per, max_cobol_lines)

    examples = []
    done_ids = set()
    if resume:
        examples = _load_jsonl(kept_path)
        done_ids = {e.get("source_id") for e in examples}
        done_ids |= {r.get("source_id") for r in _load_jsonl(attempted_path)}
        before = len(candidates)
        candidates = [c for c in candidates if c["id"] not in done_ids]
        log.info(f"resume: {len(examples)} kept on disk, skipping {before - len(candidates)} already-attempted")

    if sample and len(candidates) > sample:
        candidates = random.Random(seed).sample(candidates, sample)
        log.info(f"sampled {sample} candidates")

    total = len(candidates)
    log.info(f"{total} candidates to process | targets={targets} | workers={workers}")

    mode = "a" if resume else "w"
    kept_fh = kept_path.open(mode, encoding="utf-8")
    att_fh = attempted_path.open(mode, encoding="utf-8")
    write_lock = threading.Lock()

    stats = {"total": total, "kept": len(examples), "verified": sum(1 for e in examples if e.get("verified"))}
    skip_reasons = {}
    start = time.time()
    done = 0

    def _record(reason, example, item):
        nonlocal done
        done += 1
        with write_lock:
            att_fh.write(json.dumps({"source_id": item["id"], "reason": reason}) + "\n")
            att_fh.flush()
        if reason == "keep":
            examples.append(example)
            stats["kept"] += 1
            if example.get("verified"):
                stats["verified"] += 1
            with write_lock:
                kept_fh.write(json.dumps(example) + "\n")
                kept_fh.flush()
        else:
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
        if done % 5 == 0 or reason == "keep" or done == total:
            rate = done / max(1e-9, time.time() - start)
            eta = (total - done) / rate if rate > 0 else 0
            log.info(
                f"[{done}/{total}] {item['dataset']}/{item['id']} -> {reason} "
                f"| kept={stats['kept']} | {rate:.2f}/s | eta={eta/60:.1f}m"
            )

    if workers <= 1:
        for item in candidates:
            reason, example = _process_one(item, provider, checker, targets, keep_unverified)
            _record(reason, example, item)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_process_one, item, provider, checker, targets, keep_unverified): item
                for item in candidates
            }
            for fut in as_completed(futures):
                item = futures[fut]
                try:
                    reason, example = fut.result()
                except Exception as exc:
                    reason, example = "skip_worker_" + type(exc).__name__, None
                _record(reason, example, item)

    kept_fh.close()
    att_fh.close()

    examples, pp = _postprocess(examples, require_python_valid, gold_weight)
    stats["skip_reasons"] = skip_reasons
    stats["elapsed_seconds"] = round(time.time() - start, 1)
    stats.update(pp)
    _split_and_write(examples, out_dir, val_frac, seed, stats)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", nargs="+", default=["nist_cobol", "ibm_open_cobol"])
    ap.add_argument("--out", default="artifacts/training_data")
    ap.add_argument("--max-per", type=int, default=5000)
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--targets", choices=["rule", "llm"], default="rule")
    ap.add_argument("--provider", default="openai", choices=["openai", "anthropic", "ollama", "vllm", "local"])
    ap.add_argument("--teacher-model", default=None)
    ap.add_argument("--execution-filter", action="store_true")
    ap.add_argument("--timeout", type=int, default=15)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--keep-unverified", action="store_true")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--max-cobol-lines", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--finalize", action="store_true")
    ap.add_argument("--require-python-valid", action="store_true")
    ap.add_argument("--gold-weight", type=int, default=1)
    a = ap.parse_args()
    build(
        a.datasets, Path(a.out), a.max_per, a.val_frac, a.seed, a.targets,
        a.provider, a.teacher_model, a.execution_filter, a.timeout, a.workers,
        a.keep_unverified, a.sample, a.max_cobol_lines, a.resume, a.finalize,
        a.require_python_valid, a.gold_weight,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
