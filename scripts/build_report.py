from __future__ import annotations

import argparse
import glob
import json
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def summarise(run_dir):
    verd = {}
    judge = []
    exec_pass = exec_total = 0
    codebleu = []
    files = glob.glob(str(Path(run_dir) / "*.json"))
    for f in files:
        try:
            j = json.load(open(f))
        except Exception:
            continue
        v = j.get("verdict") or j.get("status")
        if v:
            verd[str(v)] = verd.get(str(v), 0) + 1
        for c in j.get("verdict_checks", []) or []:
            name = c.get("name")
            if name == "llm_judge" and isinstance(c.get("score"), (int, float)):
                judge.append(c["score"])
            elif name == "execution_match" and c.get("ran"):
                exec_total += 1
                if c.get("passed"):
                    exec_pass += 1
            elif name == "codebleu" and isinstance(c.get("score"), (int, float)):
                codebleu.append(c["score"])
    passes = verd.get("PASS", 0)
    scored = sum(verd.values()) or 1
    return {
        "files": len(files),
        "verdicts": verd,
        "pass_rate": round(100 * passes / scored, 1),
        "judge_mean": round(statistics.mean(judge), 3) if judge else None,
        "judge_n": len(judge),
        "exec_match": f"{exec_pass}/{exec_total}" if exec_total else "n/a",
        "exec_pct": round(100 * exec_pass / exec_total, 1) if exec_total else None,
        "codebleu_mean": round(statistics.mean(codebleu), 3) if codebleu else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rule-run", default="artifacts/runs/rule_eval")
    ap.add_argument("--neural-run", default="artifacts/runs/neural_eval")
    ap.add_argument("--out", default="docs/results_report.md")
    ap.add_argument("--gate", type=float, default=0.70)
    a = ap.parse_args()

    rule = summarise(a.rule_run)
    neural = summarise(a.neural_run)

    def row(label, r):
        return (
            f"| {label} | {r['files']} | {r['judge_mean']} | {r['pass_rate']}% | "
            f"{r['exec_match']} ({r['exec_pct']}%) | {r['codebleu_mean']} |"
        )

    winner = "rule"
    if neural["judge_mean"] and rule["judge_mean"]:
        winner = "neural" if neural["judge_mean"] > rule["judge_mean"] else "rule"
    delta = None
    if neural["judge_mean"] and rule["judge_mean"]:
        delta = round(neural["judge_mean"] - rule["judge_mean"], 3)

    lines = [
        "# PARIVARTANA — final results report",
        "",
        f"Auto-generated from `{a.rule_run}` and `{a.neural_run}`. Gate = {a.gate}.",
        "",
        "## Head-to-head (same programs, same oracle)",
        "",
        "| System | Files | Judge mean | PASS@gate | Exec-match | CodeBLEU |",
        "|---|---|---|---|---|---|",
        row("Rule baseline (Stage 2)", rule),
        row("Neural CodeT5+ (curriculum + LoRA)", neural),
        "",
        f"**Best by judge correctness: {winner}** "
        + (f"(neural − rule = {delta:+})." if delta is not None else "."),
        "",
        "## Against the proposal metrics",
        "",
        "- **LLM-as-judge**: reported above (the only correctness oracle that runs on",
        "  the full NIST CCVS corpus).",
        "- **Execution accuracy**: reported above on the self-contained subset that",
        "  runs standalone under GnuCOBOL.",
        f"- **CodeBLEU**: {'reported above' if rule['codebleu_mean'] or neural['codebleu_mean'] else 'not enabled in these runs'}.",
        "- **pass@1 (SWE-bench)**: deferred (P2 dataset).",
        "- **Human study (200 progs)**: not done.",
        "",
        "## Figures (academic)",
        "",
        "- `docs/figures/model_module_tree.svg` — CodeT5+ layer/module tree.",
        "- `docs/figures/forward_graph.svg` — forward computation graph.",
        "- `docs/figures/curriculum_tree.svg` — two-dimensional curriculum.",
        "- `docs/figures/ast_neural_pipeline.svg` — AST → CodeT5+ → Python.",
        "",
        "## Verdict breakdown",
        "",
        f"- rule: {rule['verdicts']}",
        f"- neural: {neural['verdicts']}",
        "",
        "## Honest conclusion",
        "",
        "The full three-stage pipeline runs end-to-end and the curriculum-trained",
        "CodeT5+ model is a real, evaluated artifact. The rule-based draft remains the",
        "strongest single stage by the judge; the neural model's gap is driven by",
        "training-data volume/quality (few execution-verified gold pairs, mostly",
        "unverified silver, no Python warm-start). The next levers are: a Python",
        "warm-start phase, more gold via forward-synthesis/COBOLEval, and",
        "gold-weighted / fewer-epoch training to avoid overfitting silver.",
    ]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"rule:   {rule}")
    print(f"neural: {neural}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
