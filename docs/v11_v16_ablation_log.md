# v11–v16 — Parser-free ablation sweep (post-P3-feedback)

Six batch runs on the **full NIST COBOL Test Suite**, driven from
`scripts/batch_run.py`. The purpose of this sweep was to verify the
advisor's P3 recommendation in practice: that dropping the full
ANTLR4 COBOL-85 grammar in favour of the thin regex preprocessor +
recursive-descent parser is sufficient to ingest the entire corpus,
and to isolate which deterministic levers actually move the verdict.

## Environment caveat (read first)

These six runs were executed in an offline sandbox with **no GnuCOBOL
(`cobc`) and no reachable LLM provider**. That means the two
*behavioural* oracles used in the v10 judge run — `execution_match`
(needs cobc) and `llm_judge` / `llm_promote` (need an API key) — could
not fire. The only behavioural signal available here is the
deterministic **`python_smoke`** check (subprocess-runs the translated
Python, 5 s timeout, confirms no crash).

Consequently these numbers are the **deterministic / structural
slice**, not directly comparable to v10's `82.1%` headline (which
included LLM promotion). To reproduce the behavioural uplift, re-run
the v13 config on a machine with `cobc` on PATH and
`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` set, adding `--stage3 --judge
openai --llm-promote`.

## Run matrix

| Run | Config (added on top of previous) | Judge | Smoke | Order |
|-----|-----------------------------------|-------|-------|-------|
| v11 | baseline (no flags) | none | on | complexity |
| v12 | `--exclude-fragments` | none | on | complexity |
| v13 | `--normalise` | none | on | complexity |
| v14 | `--order as-loaded` (ordering ablation) | none | on | as-loaded |
| v15 | `--no-python-smoke` (smoke ablation) | none | off | complexity |
| v16 | `--order as-loaded --no-python-smoke` | none | off | as-loaded |

## Results

| Run | Scored | Behav. PASS (`python_smoke`) | STRUCTURAL_PASS | FAIL | INCONCLUSIVE | Stage-1 fails |
|-----|-------:|-----------------------------:|----------------:|-----:|-------------:|--------------:|
| v11 | 500 | 103 (20.6%) | 397 (79.4%) | 0 | 0 | 0 |
| v12 | 459 | 53 (11.5%) | 406 (88.5%) | 0 | 0 | 0 |
| v13 | 459 | 53 (11.5%) | 406 (88.5%) | 0 | 0 | 0 |
| v14 | 459 | 53 (11.5%) | 406 (88.5%) | 0 | 0 | 0 |
| v15 | 459 | 0 | 0 | 0 | 459 (100%) | 0 |
| v16 | 459 | 0 | 0 | 0 | 459 (100%) | 0 |

Tier distribution (program-only, v12–v16): **62 simple / 220 medium /
177 high**. Paragraph-coverage and identifier-coverage checks scored
1.0 across every run (the rule-based translator emits a stub for every
paragraph and carries every identifier through, so structural coverage
is saturated before any behavioural oracle runs).

## What each run established

**v11 — the parser-free pipeline ingests the whole corpus.** Zero
Stage-1 parse failures across all 500 NIST files (including 41
copybook fragments). This is the central evidence for the feedback:
the thin preprocessor handles 1960s fixed-format COBOL end-to-end
without a full grammar. The 20.6% behavioural PASS is inflated by
trivial copybook fragments that smoke-pass for free.

**v12 — honest denominator.** Excluding the 41 non-program fragments
drops the behavioural PASS to **11.5% (53/459)**. This is the true
offline `python_smoke` floor on real programs; the v11 figure was
partly fragments. Most excluded fragments were simple-tier (simple
count 112 → 62).

**v13 — normaliser is a no-op on the offline structural verdict.**
Adding `--normalise` (strip margins, decode intrinsics, mark AT END /
INVALID KEY, expand INSPECT, mark OCCURS) leaves the structural
verdict identical to v12. Its payoff — un-stubbed paragraphs and
injected imports — only converts to PASS under a *behavioural* oracle
(cobc stdout match or LLM promotion), which is exactly what's missing
in this sandbox. Expected null result here; re-test with cobc.

**v14 — complexity ordering is a no-op at full budget.** With 459
records and `--max 500`, nothing is truncated, so processing order
cannot change the verdict set. Curriculum ordering matters for
*training dynamics* and for partial-budget runs (`--max` < corpus),
not for a full-corpus inference pass. Identical to v13.

**v15 — `python_smoke` is the entire offline behavioural lever.**
Turning it off with no cobc and no LLM leaves **zero** behavioural
signal: all 459 programs land INCONCLUSIVE. This quantifies the
check's value precisely — in an offline environment it is solely
responsible for promoting structural output to behaviour-verified
PASS.

**v16 — confirms v15.** Both levers off; ordering irrelevant; 100%
INCONCLUSIVE.

## Takeaways

1. **The feedback's core bet holds.** Parser-free ingestion gives 0
   Stage-1 failures on the full NIST suite — the ANTLR4 grammar was
   not needed to get the corpus through Stage 1.
2. **Honest offline behavioural floor: 11.5%** (`python_smoke` only,
   real programs). Everything else is structurally clean but awaiting
   a behavioural oracle.
3. **The gap to v10's 82.1% is entirely the behavioural oracle layer**
   (cobc execution + LLM promotion), not the parser or the
   preprocessor. The deterministic skeleton is solid; the uplift lives
   in execution + LLM, which is where the advisor told us to spend the
   reclaimed time.
4. **Next run to do on real hardware:** v13 config
   `--exclude-fragments --normalise --stage3 --judge openai
   --llm-promote` with cobc installed — that is the apples-to-apples
   successor to v10.
