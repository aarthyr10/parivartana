# v9 — Recovering the PASS verdicts v7/v8 lost

## What v8 broke on your Mac

```
v6 Mac:  PASS=74  STRUCTURAL_PASS=289  FAIL=96   headline=79.1%
v7 Mac:  PASS=44  STRUCTURAL_PASS=321  FAIL=94   headline=79.5%
v8 Mac:  PASS=49  STRUCTURAL_PASS=322  FAIL=88   headline=80.8%
```

Headline kept inching up (79.1 → 80.8 %) — but actual PASS dropped
from 74 → 49 between v6 and v8. **My v7 change was too aggressive:**
I auto-skipped `execution_match` for any program using `OPEN`, `READ`,
`WRITE`, `CLOSE`, `ACCEPT`, reasoning that file-I/O programs
"couldn't run cleanly in a sandbox." That was wrong: `cobc` is the
runtime for the COBOL side and it handles file errors itself; the
rule-based Python wraps file ops in `try / except` blocks that
quietly set `state['_file_status']`. On v6 those programs were
matching stdout cleanly and earning real PASS.

Confirmation: 69 of the 74 v6 PASS programs reverted to
STRUCTURAL_PASS in v8, *all* with `execution_match: skipped — uses
I/O verbs requiring environment`. Sample: `IC222A` had
`execution_match: PASS — stdout matched` in v6 and `execution_match:
skipped` in v8.

## Three fixes in v9

### 1. Rollback execution_match's I/O auto-skip (`src/evaluation/verifier.py`)

`_check_execution` no longer short-circuits on file-I/O programs.
The `_program_needs_runtime_env` helper still exists and is still
called by `_check_python_smoke` (Python's `open()` raises on missing
files in a way the rule-based template doesn't suppress), but
execution_match runs again and `cobc` decides whether the COBOL
side ran cleanly. The 69 lost PASS verdicts should come back.

### 2. Make the LLM rescue visible even when it fails (`src/evaluation/verifier.py`)

In v8 the rescue *was* attempted on the user's Mac, but both
providers 429/401'd — the rescue silently returned `rescued=False`
and the synthetic `llm_rescue` check never appeared in
`verdict_checks`. So `patterns.json` showed `llm_rescued = 0` and
the user couldn't tell whether the rescue ran or not.

We now append a `llm_rescue` check to the trace even when no
provider succeeded — with `ran=False`, `skipped_reason=` containing
every provider's failure (e.g. `"openai: judge call failed (429
You exceeded your current quota...) | anthropic: judge call failed
(401 invalid x-api-key)"`). The verdict stays FAIL (rescue didn't
save it) but the trace explains *why* the safety net didn't kick in.

### 3. Twenty more intrinsic functions (`src/pipeline/stage1_parser/normaliser.py`)

The remaining 84 v8 `body_non_trivial` FAILs clustered around NIST
arithmetic-test paragraphs (`MPY-TEST-F1-3-0`, `DIV-TEST-F2-3-0`,
`F-ATAN-TEST-01`, `F-COS-TEST-12`, `F-DATE-OF-INTEGER-TEST-01`, etc.).
These programs use COBOL intrinsics that our R2 normaliser didn't
have entries for, so the IF expressions in those paragraphs ended up
unparseable and the bodies stubbed.

Added entries for: `SIN`, `COS`, `TAN`, `ASIN`, `ACOS`, `ATAN`,
`EXP`, `EXP10`, `PI`, `E`, `CURRENT-DATE`, `WHEN-COMPILED`,
`DATE-OF-INTEGER`, `DATE-TO-YYYYMMDD`, `DAY-OF-INTEGER`,
`DAY-TO-YYYYDDD`, `INTEGER-OF-DATE`, `INTEGER-OF-DAY`,
`YEAR-TO-YYYY`, `FACTORIAL`, `SUM`, `STORED-CHAR-LENGTH`,
`TEST-NUMVAL`, `TEST-NUMVAL-C`.

Each maps to a Python expression using `math` or `datetime` stdlib
(`SIN` → `math.sin`, `DATE-OF-INTEGER` → a `datetime.date(1601,1,1) +
timedelta(days=N-1)` formula matching the COBOL spec, etc.). The
needed import is auto-tracked.

This should unstub a meaningful chunk of the 84 body_non_trivial
FAILs — probably 30-50 of them.

## Expected v9 result on the Mac

| outcome              | v8 count | v9 estimate |
|----------------------|---------:|-------------:|
| PASS (behav.)        |       49 |       ~115-130 |
| STRUCTURAL_PASS      |      322 |       ~280-300 |
| FAIL                 |       88 |        ~35-50 |
| **HEADLINE PASS%**   |  **80.8%** |  **~89-92 %** |

The big lift comes from rollback (1): ~69 programs flip from
STRUCTURAL_PASS to PASS without changing total headline. The
intrinsic expansion (3) drops ~30 FAILs into STRUCTURAL_PASS
(or PASS where the program is I/O-free). The rescue visibility (2)
doesn't change the verdict — it just makes the failure mode legible.

## Sandbox smoke (no keys, no cobc)

Still **459/459 = 100 % headline** with **0 FAIL**, same as v8 (the
sandbox can't exercise the rollback because cobc isn't installed
there).

## Run command (v9)

```bash
cd /Users/aarthy/projects/nwu/parivartana && source .venv/bin/activate

nohup python scripts/batch_run.py \
    --dataset nist_cobol --max 500 --judge openai --stage3 \
    --judge-model gpt-4o-mini --stage3-min-tier medium \
    --normalise --cobc-preflight --exclude-fragments \
    --llm-rescue \
    --run-id full_500_judge_v9 --order complexity \
    > /tmp/parivartana_batch_v9.out 2>&1 &
tail -f artifacts/runs/full_500_judge_v9/progress.csv
```

## Files changed

```
src/evaluation/verifier.py                    +30  rollback I/O skip,
                                                   visible failed rescue
src/pipeline/stage1_parser/normaliser.py      +35  20 more intrinsic functions
docs/v9_pass_regression_fix.md                 +    this file
```

146 unit tests still pass.
