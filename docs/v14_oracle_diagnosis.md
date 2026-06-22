# v14 oracle run — why it's slow, why it "fails", and the honest metric

Diagnosed from the real Mac traces in `artifacts/runs/full_v14_nist`
(128 programs scored before you stopped it: 2 PASS, 126 FAIL).

## Two separate problems

### 1. Slow — fixed
Every program made heavy LLM calls: Stage-3 refine **plus** the full
five-dimension `llm_judge`, each sending the *entire* COBOL + Python to
the *default (gpt-4o-class)* model, sequentially, and getting slower as
complexity-ordered programs grow. ~40 s/program → ~5 h for 459.

Fixes applied:
- `--judge-model` now defaults to **gpt-4o-mini** (~30× cheaper, much faster).
- `LlmJudge.score()` now **truncates COBOL/Python to 6 KB each** before
  prompting, so big programs don't blow up latency/cost.

### 2. "Everything fails" — this is mostly honest, not a bug
The per-program checks tell the real story:
- All structural checks pass; `python_smoke` passes (v14 made things run).
- **`execution_match` is SKIPPED** — `cobol side could not be executed
  (rc=1)`. NIST programs are CCVS *test-harness* programs that don't run
  standalone under GnuCOBOL, so there is **no execution oracle** for them.
- **`llm_judge` gates the verdict** and fails 122/126: it scores
  rule-based output at correctness 0.2–0.7, weighted < the 0.70 pass
  threshold → FAIL.

So the low pass rate is the LLM judge honestly rating the **rule-based
translation quality as mediocre** — not a crash or a pipeline break.

## Why this looks like a regression from v10's 82% (but isn't)
v10's headline counted two things that masked true quality:
1. **STRUCTURAL_PASS** (structure clean, behaviour never tested) — 249 of
   459, over half the headline.
2. The `llm_judge` in v10 was **rate-limited (429-skipped)**, so it never
   gated anything (see `docs/v9_promote_bridge.md`).

When the judge actually runs (as now), it reveals the real correctness,
which was always low. v10 was an over-count, not a peak we regressed from.

## A caution about the v14 I/O changes
The v14 no-crash work (paragraph stubs `def x(): pass`, `(state[x] or 0)`
everywhere, `open(name,'a').close()` touches, EOF→AT END) makes programs
*run*, but it makes the generated code **hackier**, which the judge
penalises on correctness/pythonic. In other words, optimising the
no-crash metric can actively *lower* the judge metric. The two goals
diverge.

## The honest path forward (not metric-gaming)
1. **Measure the right thing.** For NIST, `execution_match` can't run, so
   report the **llm_judge score distribution** (mean correctness), not a
   binary 0.70 pass rate. A rule-based transpiler scoring ~0.5 is the real
   baseline.
2. **The quality lever is Stage-3 LLM refinement.** The proposal's design
   is rule-based draft → **LLM rewrites it into clean, correct Python**.
   If refinement worked well the judge would score the *refined* code
   high. Investing in the refiner prompt/quality is what raises the real
   success rate — far more than no-crash hacks.
3. **The neural model** (fine-tuned CodeT5+) is the other real lever, and
   still needs a trained checkpoint.
4. **Pick an executable eval set** if you want true execution_match: small
   self-contained COBOL (not CCVS harness programs) that GnuCOBOL can run
   standalone.

## Fast command (minutes, not hours)
```
python scripts/batch_run.py --dataset nist_cobol --max 2000 \
    --judge openai --judge-model gpt-4o-mini --run-id v14_fast
```
Drop `--stage3` for the fastest diagnostic (one judge call/program). Add
it back only when measuring refined-code quality. Expect a low but
*honest* pass rate; use the score distribution, not the 0.70 binary, as
the headline.
