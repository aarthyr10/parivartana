# v9.1 — Bridging STRUCTURAL_PASS to PASS with a cheap LLM verifier

## The PASS vs STRUCTURAL_PASS gap, measured

Comparison across the v8 full-Mac run (459 programs):

|                                | PASS (49)       | STRUCTURAL_PASS (322) |
|--------------------------------|-----------------|-----------------------|
| Avg paragraphs                 | 5               | 97.7                  |
| Avg COBOL bytes                | 5,920           | 66,128                |
| Tier mix (simple/medium/high)  | 48 / 1 / 0      | 10 / 191 / 121        |
| Uses file I/O                  | 2 / 49 (4 %)    | 321 / 322 (99.7 %)    |
| Uses `ACCEPT` (stdin)          | 0 / 49          | 107 / 322 (33 %)      |
| `python_smoke` outcome         | 49 pass         | 322 skipped (env)     |
| `execution_match` outcome      | 10 pass, 39 cobol-side error | 322 skipped (env, my v7 bug) |
| `llm_judge` outcome            | 49 429-skipped  | 322 429-skipped       |

The story is unambiguous: **STRUCTURAL_PASS programs are large
file-I/O test suites** that the python_smoke check truly can't
exercise (Python's `open()` raises on missing files) and where the
v7 auto-skip on execution_match bit hardest. v9 already rolls back
the execution_match auto-skip — that alone should flip ~69 programs
back to PASS via stdout match.

For the remaining ones — programs where stdout *doesn't* match
exactly (or where cobc errors before producing comparable output) —
we need a different bridge. Hence the new `llm_promote` check.

## What `llm_promote` does

A single binary question to a cheap model: *"is this Python a
faithful translation of this COBOL?"*

- **Inputs:** COBOL source (truncated to 8 kB) + the candidate
  Python (truncated to 8 kB).
- **Prompt:** very tight system message — *say YES if the Python
  covers the major operations, uses idiomatic Python, doesn't crash
  at import, matches the COBOL intent. Say NO if paragraphs are
  missing, arithmetic is wrong, output verbs were dropped,
  identifiers absent.*
- **Output:** one line — `YES` or `NO`, optionally followed by a
  short reason.

When the model says `YES`, the verdict flips from `STRUCTURAL_PASS`
to `PASS` and a synthetic `llm_promote` check lands in the trace
with provenance:

```json
{
  "name": "llm_promote",
  "ran": true,
  "passed": true,
  "score": 1.0,
  "detail": "promoted via openai: YES — covers all paragraphs, arithmetic ok",
  "extra": {
    "promoted": true,
    "provider": "openai",
    "reason": "covers all paragraphs, arithmetic ok",
    "attempts": ["openai: YES — covers all paragraphs, arithmetic ok"]
  }
}
```

When the model says `NO`, the verdict stays `STRUCTURAL_PASS`
(honest — the LLM didn't think the translation was good enough)
and the synthetic check records `passed=False` so you can see
what the LLM said.

When neither provider can be reached (no key, 429), the
synthetic check records `ran=False` with the provider errors in
`skipped_reason` — same pattern as the rescue's visible-failure
mode.

## Cost

| dimension                | rubric `llm_judge` | `llm_promote` |
|--------------------------|-------------------:|--------------:|
| Input tokens / program   | ~5 000             | ~5 000        |
| Output tokens / program  | ~500 (rubric+rationale) | ~10 (YES/NO) |
| gpt-4o-mini $ / program  | ~$0.001            | ~$0.0008      |
| 322 STRUCTURAL_PASSes    | $0.32              | **$0.26**     |

Cheap enough that we could fire it on every STRUCTURAL_PASS without
thinking twice.

## Honesty discipline

`PASS` via `llm_promote` is a softer signal than `PASS` via
`execution_match` (which is byte-equality with cobc's actual stdout).
The verdict ladder, ranked by confidence:

```
PASS  ← execution_match stdout match   (deterministic, byte-equal)
PASS  ← python_smoke clean run         (deterministic, no crash)
PASS  ← llm_judge rubric ≥ 0.70        (5-dim rubric)
PASS  ← llm_promote YES                (1-bit LLM verdict)  ← new
STRUCTURAL_PASS                        (4 structural checks)
FAIL                                   (any structural check failed)
```

A reviewer can still tell what kind of PASS each program earned by
looking at which check passed in `verdict_checks`. The Past Runs
page already shows this. The headline number just becomes more
useful — closer to "real translation quality" than "tests we
ran in our sandbox."

## Expected v9 + promote result on your Mac

| outcome           | v8 actual | v9 estimate | v9 + promote estimate |
|-------------------|----------:|-------------:|-----------------------:|
| PASS (behav.)     |        49 |       ~120 |              ~310-340 |
| STRUCTURAL_PASS   |       322 |       ~280 |              ~30-60   |
| FAIL              |        88 |       ~50  |              ~50      |
| **HEADLINE PASS%**|  **80.8%** |  **~89-92%** |        **~89-92 %** (same, but more behaviour-verified) |

The headline number doesn't move much because v9's rollback already
took it to ~90 %. The promote check shifts the *composition* of that
90 % — moving from "90 % structural-only" to "65-75 % behaviour-or-
LLM-verified, 5-10 % structural-only." That's the meaningful change.

## Run command (v9 with rescue + promote)

```bash
cd /Users/aarthy/projects/nwu/parivartana && source .venv/bin/activate

nohup python scripts/batch_run.py \
    --dataset nist_cobol --max 500 --judge openai --stage3 \
    --judge-model gpt-4o-mini --stage3-min-tier medium \
    --normalise --cobc-preflight --exclude-fragments \
    --llm-rescue \
    --llm-promote \
    --run-id full_500_judge_v9 --order complexity \
    > /tmp/parivartana_batch_v9.out 2>&1 &
tail -f artifacts/runs/full_500_judge_v9/progress.csv
```

Total expected LLM spend (gpt-4o-mini):

- Stage 3 LLM refinement: ~$0.20 (one call per medium/high program,
  ~$0.001 each, ~350 programs after the tier gate)
- LLM judge rubric on programs that get there: ~$0.20
- LLM rescue on FAILs: ~$0.05 (~50 programs × $0.001)
- LLM promote on STRUCTURAL_PASSes: ~$0.26 (322 × $0.0008)

**Total: ~$0.70 for a full 500-program run.**

If you want a cheaper "promotion-only" run that skips the more
expensive Stage 3 and rubric judge:

```bash
nohup python scripts/batch_run.py \
    --dataset nist_cobol --max 500 --judge openai \
    --judge-model gpt-4o-mini \
    --normalise --cobc-preflight --exclude-fragments \
    --llm-promote \
    --run-id full_500_promote_only --order complexity \
    > /tmp/parivartana_batch_promote.out 2>&1 &
```

That's ~$0.26 end-to-end and still flips the headline.

## Patterns we now bucket

`patterns.json` now exposes:

- `llm_promoted` — count of STRUCTURAL_PASS → PASS lifts, keyed by provider
- `llm_promote_rejected` — count of LLM saying "NO" (honest STRUCTURAL_PASS keeps)
- `llm_promote_unavailable` — count of attempted-but-no-provider promotions

So you can tell at a glance how many programs the LLM vetted and
how many it rejected.

## Files changed in v9.1

```
src/evaluation/llm_promote.py                +110  new module
src/evaluation/verifier.py                   +95   promote plumbing, synthetic check
scripts/batch_run.py                          +20  --llm-promote flag, promote bucket
docs/v9_promote_bridge.md                     +    this file
```

All 146 unit tests still pass.
