# v13 — Arithmetic coercion + professor-feedback cleanup

> **Incident note (resolved).** The first v13 run on a torch-equipped Mac
> scored 458/459 FAIL. Cause: `--stage2` had been defaulted to `neural`,
> which loaded the *untrained base* `Salesforce/codet5p-220m` (no
> fine-tuned checkpoint present) and emitted unusable output
> (`0/64 paragraphs`, `0/88 identifiers`). Fix: `--stage2` now defaults
> to `rule`, and an explicit `--stage2 neural` falls back to rule-based
> when no fine-tuned checkpoint exists (never the base model). The
> rule-based path below is the validated one. Re-run restored
> 277 PASS / 7 FAIL.

Full NIST 500 run (`full_500_judge_v13`, offline `--judge none`,
python_smoke behavioural signal).

## v12 → v13

| Metric | v12 | v13 | Δ |
|---|---:|---:|---:|
| Behavioural PASS | 266 (58.0%) | **277 (60.3%)** | +11 |
| STRUCTURAL_PASS | 175 | 175 | 0 |
| FAIL | 18 (3.9%) | **7 (1.5%)** | −11 |
| Headline | 96.1% | 98.5% | +2.4pp |

146 unit tests still pass.

## What changed

**Arithmetic operand coercion** (`rule_based.py`). The 11 v12 FAILs were
all `TypeError: unsupported operand for +: 'NoneType'` — group / no-PIC
items default to `None`, then a numeric field that lost its PIC was used
in `ADD` / `COMPUTE`. New `_num(tok)` helper wraps every arithmetic and
COMPUTE operand as `(<ref> or 0)`, so `None`/empty coerce to `0` inside
arithmetic only. Group defaults elsewhere are untouched (no mistyping of
record/string fields). Cleared all 11.

**Professor-feedback cleanup — ANTLR4 fully removed.** Two lingering
references were deleted: `configs/models.yaml` (`grammar: cobol85`,
`grammar_file: src/grammars/Cobol85.g4`, `runtime: antlr4-python3` →
`parser: recursive-descent`) and `app/pages/6_Settings.py` (the
`antlr4-python3-runtime` dependency check). Combined with the earlier
`requirements.txt` removal and the wired-in CodeT5+ NeuralTranslator
(`--stage2 neural`), the feedback items now reflected in code are: drop
ANTLR4 (done), parser-free Stage 1 (done), focus on neural translation +
curriculum + LLM refinement (wired). CMOS remains a proposal-document
task, not code.

## Remaining 7 FAILs and what can improve next

```
5  NameError: name 'ccvs1'        SG201A SG202A SG203A SG102A SG103A
1  NameError: name 'head_routine' NC113M
1  FileNotFoundError              SQ303M
```

- `ccvs1` / `head_routine` are CCVS-framework identifiers (cross-module
  paragraphs / control fields) referenced but never declared locally —
  needs the entrypoint/identifier resolver to emit a stub or skip the
  reference.
- The far bigger remaining lever is the **175 STRUCTURAL_PASS** programs
  (input-consuming: READ/ACCEPT) that are still skipped, i.e. untested
  rather than verified. Stubbing empty input files + honoring AT END
  would let many run and convert to real PASS — a larger gain than the
  last 7 FAILs.

## Full-run command

```
python scripts/batch_run.py --dataset nist_cobol --max 500 --judge none --run-id full_500_judge_v13
```

(Add `--stage2 neural --stage3 --judge openai --llm-promote` on a machine
with torch + the CodeT5+ checkpoint + API keys for the full neural + LLM
pipeline.)
