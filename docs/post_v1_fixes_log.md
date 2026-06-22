# Post-v1 fixes & next-steps record

Record of every change applied after the `full_500_judge` run (Run 1)
revealed 0 PASS, 25 FAIL, 475 INCONCLUSIVE. Three subsequent runs +
eight follow-up steps below.

## Runs at a glance

| Run id                       | PASS | FAIL | INCONCLUSIVE | Trigger                                                  |
|------------------------------|-----:|-----:|-------------:|----------------------------------------------------------|
| `full_500_structural`        |    0 |    1 |          499 | First CLI batch, no judge                                |
| `full_500_structural_v2`     |    0 |    0 |          500 | After verifier ↔ translator `_snake()` alignment         |
| `full_500_judge`             |    0 |   25 |          475 | First full run with judge + Stage 3 (Anthropic 401 hid OpenAI errors; Stage 3 truncated 25 programs) |
| `full_500_judge_v2`          |    0 |    0 |          500 | After truncation guard + JSON-fence strip + multi-provider error capture |
| `full_500_judge_v3`          |    0 |    0 |          500 | With `--judge-model gpt-4o-mini`; same `429 insufficient_quota` from OpenAI |

Net structural result after fixes: **0 syntax failures, 0 paragraph
coverage failures, 0 identifier coverage failures, 500/500 Stage 3
ran cleanly, 0 truncation signals.**

PASS remains 0 only because both LLM providers are unavailable:
OpenAI is out of credits (429), Anthropic key is invalid (401).
Once one provider works, headline PASS rate should jump immediately.

## Code changes

### Run 1 → Run 2 (`full_500_structural` → `full_500_structural_v2`)

1. **`src/evaluation/verifier.py`** — `_snake()` now delegates to the
   translator's `_snake()`, so paragraph names like `PASS`, `CLASS`,
   `RETURN`, `GLOBAL` are searched as `pass_`, `class_`, `return_`,
   `global_` (matching what the translator actually emits). Fixed
   374/500 sub-1.0 paragraph coverage scores and the single
   `NC110M` FAIL.

### Run 2 → Run 3 (`full_500_judge` → `full_500_judge_v2`)

2. **`src/pipeline/stage3_llm/providers.py`** — default `max_tokens`
   raised from 2048 → 8192 on both `OpenAIProvider` and
   `AnthropicProvider`. `LLMResponse` now carries `finish_reason`
   and `truncated` flags.

3. **`src/pipeline/stage3_llm/refiner.py`** — when
   `response.truncated` is true, discard the partial output and keep
   the renamed code. Tags `metadata["llm_truncated"]=True` so the
   batch runner buckets it into `patterns.json`.

4. **`src/evaluation/judge.py`** — new `_extract_json()` strips
   ```json``` fences and slices the outermost `{ … }` from
   conversational preambles. The judge error message now surfaces
   the provider name and finish_reason for debuggability.

5. **`src/evaluation/verifier.py`** — `_check_llm_judge` concatenates
   all provider attempts into `skipped_reason` with ` | `, so an
   OpenAI failure can no longer be hidden by an Anthropic 401 that
   came later in the chain.

6. **`scripts/batch_run.py`** — fixed the `result.rename_map`
   `AttributeError` (real field is `metadata["renamed_identifiers"]`)
   and persisted `check.extra` into the trace JSON so
   `providers_tried`, paragraph found/missing lists, and judge
   components survive the round-trip.

### Run 3 → Run 4 follow-ups (current commit)

7. **`scripts/batch_run.py` — `--judge-model` flag** — lets the
   user override the model the judge uses (e.g. `gpt-4o-mini` for
   ~30× cheaper scoring) without touching code. Plumbed end-to-end
   through `verify(..., llm_model=...)` → `_check_llm_judge(...,
   model=...)` → `get_provider(name, model=...)`.

8. **`src/evaluation/judge.py` — judge result cache** — file-backed
   cache at `artifacts/cache/judge_cache.json` keyed by
   `(provider, model, sha256(cobol), sha256(python))`. Re-runs after
   a config-only change skip every previously-scored program.
   Atomic writes via a `.tmp` sibling; thread-safe via a module-level
   lock. Cached components are stored, not the weighted score, so
   tweaking weights doesn't invalidate cache hits.

9. **`scripts/batch_run.py` — `--stage3-min-tier` flag** — gate
   Stage 3 refinement on complexity tier. Default `simple` matches
   previous behaviour. Set `--stage3-min-tier medium` to skip
   refinement on the ~112/500 simple-tier NIST programs (rule-based
   output is already clean for them; saves ~25 % of LLM spend).
   Skipped programs are bucketed into `patterns.json` so usage is
   visible.

10. **`tests/unit/test_post_v1_fixes.py`** — 20 regression tests
    locking in all four post-v1 fixes plus the new cache behaviour:

    - `_snake()` parity between verifier and translator (8 cases)
    - Paragraph `PASS` is found after the fix
    - Refiner discards truncated output, keeps complete output
    - `_extract_json` handles six common LLM verbosity patterns
    - Judge uses `_extract_json` end-to-end via a fake provider
    - `skipped_reason` concatenates all provider attempts
    - Judge cache avoids the second API call on identical inputs

    Total unit-test count went from 105 → 125; all green.

## Step-8 spot check (no regression in -51 line outlier)

`IX215A` had the biggest Stage 3 → Stage 2 line drop in
`full_500_judge_v3` (-51 lines on a 2,710-line file). Confirmed:

- Stage 2 emits 214 functions; Stage 3 also emits **214** functions
- 0 functions dropped, 0 added
- All three structural checks pass with score 1.0
- Last lines of refined code terminate cleanly (no mid-string cutoff)

The drop is the LLM compacting one-liners, not losing content. The
truncation guard is doing its job.

## User-side blockers (not code)

Two of the eight follow-up steps need action outside this repo:

- **OpenAI credit.** `full_500_judge_v2` and `_v3` both hit
  `429 insufficient_quota` on every call. Either top up the billing
  account at <https://platform.openai.com/account/billing> or wait
  for the monthly limit to reset.

- **Anthropic key.** Current key in `.env` returns
  `401 invalid x-api-key`. Rotate it at
  <https://console.anthropic.com/settings/keys> so the fallback chain
  actually has a fallback.

- **GnuCOBOL** (optional, free behavioural signal). `brew install
  gnu-cobol` on the Mac. The batch runner auto-detects `cobc` on
  PATH and enables `execution_match` — a deterministic check that
  doesn't need any LLM at all.

## Recommended next command

Once at least one provider works, this is the canonical command:

```bash
cd /Users/aarthy/projects/nwu/parivartana && source .venv/bin/activate
nohup python scripts/batch_run.py \
    --dataset nist_cobol --max 500 --judge openai --stage3 \
    --judge-model gpt-4o-mini \
    --stage3-min-tier medium \
    --run-id full_500_judge_v4 --order complexity \
    > /tmp/parivartana_batch_v4.out 2>&1 &
tail -f artifacts/runs/full_500_judge_v4/progress.csv
```

The cache will already be cold on a fresh `run_id`, but a follow-up
re-run with the same inputs (different `--run-id`) will pay nothing
for the judge calls thanks to step 8.
