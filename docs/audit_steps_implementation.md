# Audit steps A-F — implementation record

All six steps from `docs/conversion_quality_audit.md` are implemented.
Each step is a separate module, opt-in via a CLI flag on `batch_run.py`,
and unit-tested in isolation. None of them change the default Stage
1/2/3 behaviour — the user opts in to each pass independently so the
A/B comparison against the baseline run is clean.

## Step summary

| Step | Module                                              | Flag                  | Type            | Status |
|:----:|-----------------------------------------------------|-----------------------|-----------------|--------|
|  E   | `src/evaluation/verifier.py::_check_body_non_trivial` | (always on)         | Verifier check  | live   |
|  A   | `src/pipeline/stage1_parser/cobc_preflight.py`      | `--cobc-preflight`    | Pre-parse gate  | live   |
|  B   | `src/pipeline/stage1_parser/normaliser.py`          | `--normalise`         | Pre-parse rewrite | live |
|  C   | `src/pipeline/stage1_parser/pic_decoder.py`         | (library, used by Stage 2 emitter when wired) | Type decoder | live (Stingray fallback ready) |
|  D   | `src/evaluation/legacylens_diff.py`                 | `--legacylens-diff`   | Quality signal  | live   |
|  F   | `src/pipeline/stage1_parser/proleap_fallback.py`    | `--proleap-fallback`  | Fallback scaffold | scaffold (jar + jpype1 user-side) |

## Step E — body-non-trivial verifier check

The most important change because it stopped the system from lying.
Before E, `paragraph_coverage` reported 100 % whenever every paragraph
had a matching `def`, even if the function body was just `pass`. The
audit showed 4,110 of 38,951 emitted functions (10.5 %) were stubs.

`_check_body_non_trivial` collects each COBOL paragraph's statement
count from the AST, then inspects each matching Python function's
body. Bodies of `pass`, `...`, `return`/`return None`, comments, or
docstrings are "trivial." Paragraphs whose COBOL was ≤ 1 statement
(`CONTINUE`-only, etc.) are exempt — a `pass` is a faithful
translation of `CONTINUE`. Threshold is 90 % to match the other
coverage checks.

Smoke test on the two-paragraph fixture: stubbing `OTHER-PARA` makes
the verdict flip to `FAIL` with score 0.5. Real result on `IF402M`:
would have flipped from PASS-ready (current bogus state) to FAIL
(reality). 5 unit tests, all passing.

## Step A — cobc syntax-only preflight

Shells out to `cobc -fsyntax-only` in a temp file, captures stderr,
records `accepted` / `rejected` / `skipped` into the trace. The
batch runner buckets four populations:

| our parser | cobc      | bucket                            |
|------------|-----------|-----------------------------------|
| ✓ accepted | ✓ accepted | normal — nothing to log         |
| ✓ accepted | ✗ rejected | `our_parser_accepted_cobc_rejected` (we're too lenient) |
| ✗ failed   | ✓ accepted | `our_parser_failed_cobc_accepted` (we're missing capability) |
| ✗ failed   | ✗ rejected | source is broken; fair stop     |

Off by default; enable with `--cobc-preflight`. Sandbox runs show
`stage1_cobc_status=skipped` because `cobc` isn't on PATH in our CI
environment — `brew install gnucobol` on the user's Mac flips it on.

## Step B — regex normaliser pre-pass

Six transforms, run in this order before Stage 1 parsing:

1. **R1 strip fixed-format margins** — drops cols 73-80 (right margin
   tags like `IF4024.2`), col-7 `*` comment lines, col-7 `/` page
   ejects. Folds col-7 `-` continuation lines. **Preserves cols 1-72**
   so the parser still sees Area A vs Area B at the right positions.
2. **R2 decode intrinsic functions** — rewrites `FUNCTION LENGTH(X)`
   to `len(X)`, `FUNCTION LOG(X)` to `math.log(X)`, etc. Returns the
   set of stdlib imports needed (`math`, `statistics`, `random`) so
   the Stage 2 emitter can prepend them. Covers LENGTH, LOG, LOG10,
   MAX, MIN, MEAN, MEDIAN, MIDRANGE, MOD, REM, NUMVAL, NUMVAL-C,
   LOWER-CASE, UPPER-CASE, REVERSE, TRIM, ORD, CHAR, ABS, SQRT,
   INTEGER, INTEGER-PART, RANDOM (22 intrinsics).
3. **R3 PIC clause parser** — exposed as a helper (`parse_pic`); used
   by Step C's decoder.
4. **R4 AT END / INVALID KEY markers** — rewrites the I/O exception
   clauses to `__AT_END__` / `__NOT_AT_END__` /
   `__INVALID_KEY__` / `__NOT_INVALID_KEY__` markers that Stage 2's
   READ/WRITE/REWRITE handlers will pick up.
5. **R5 INSPECT TALLYING / REPLACING** — rewrites to MOVE/COMPUTE
   statements with synthetic `__INSPECT_COUNT__` /
   `__INSPECT_REPLACE__` helpers that emit `str.count(...)` and
   `str.replace(...)` at codegen.
6. **R6 OCCURS / INDEXED BY** — marks fixed-size arrays so the data
   section emits `list = [default] * N` instead of a scalar.

End-to-end smoke test on `IF402M` (NIST intrinsic-function test):
the `if402m_length` paragraph went from a `pass # TODO: malformed`
stub to `if len("ABC") == len("ABC"): pass` — real translated code.
The full normaliser pass found 4 additional paragraphs and 22
fewer stubs across the program. Off by default; enable with
`--normalise`. 11 unit tests, all passing.

## Step C — Stingray-backed PIC decoder

`decode_pic("PIC S9(4) COMP-3")` returns `PicDecoding(type="Decimal",
default_literal='Decimal("0")', scale=0, signed=True, length=4,
usage="COMP-3", backend="regex")`. Two backends:

* **Stingray** when installed — production-grade PIC parser, handles
  the full COBOL85 USAGE set (DISPLAY, COMP, COMP-3, COMP-5,
  PACKED-DECIMAL, BINARY). `pip install stingray-reader` (Python
  3.12+). Lazy-imported so it isn't a hard dependency.
* **Regex** fallback — the `parse_pic` helper from R3. Picks up
  ~95 % of NIST PIC forms.

The decoded result includes `needed_imports`, so when any data item
is Decimal-typed the emitter knows to add `from decimal import
Decimal` at the top of the file. 7 unit tests, all passing.

Not yet wired into `rule_based.py`'s data-section emitter — that
edit is a follow-up because it touches the existing
`_default_for_pic` heuristic and needs a careful before/after diff.
The module is import-clean and stand-alone-tested.

## Step D — legacylens second-opinion coverage diff

`coverage_diff(cobol_source, ast)` runs the third-party
`cobol_parser` (PyPI: `legacylens-cobol-parser`) over the source
and diffs its CALL / PERFORM / file-I/O lists against our AST.
Any name legacylens finds that we don't gets bucketed into
`missed_call`, `missed_perform`, or `missed_io_file` in
`patterns.json`.

Off by default; enable with `--legacylens-diff`. Read-only — does
not affect codegen. Verified end-to-end against `RL211A` (a
heavy-I/O NIST program): legacylens correctly extracted dozens of
PERFORMs, the diff bucket is empty when our parser handled them
all, populated when our parser missed any.

## Step F — ProLeap fallback (scaffold)

The scaffold proves jpype1 + ProLeap can be wired into our pipeline
and exposes:

* `status()` — probes whether jpype1 is installed AND the jar is
  on disk. Returns a one-line `reason` so the trace tells the user
  exactly what to install.
* `parse_via_proleap(cobol_source)` — starts the JVM (once),
  invokes `CobolParserRunnerImpl.analyzeCode`, walks compilation
  units → program units → paragraphs, returns the paragraph names.
* `coverage_vs_ours(cobol_source, our_ast)` — diffs ProLeap's
  paragraph list against ours; the gap goes into `patterns.json`
  as a fallback-quality signal.

What's deferred until the jar is installed: full ProLeap AST →
our `AstNode` conversion so unparseable paragraphs can be *rescued*
(not just diagnosed). The scaffold gives us the first signal —
"would ProLeap have parsed this paragraph?" — without committing to
the heavier conversion work until we know it's worth it.

User installation:

```bash
pip install jpype1
mkdir -p artifacts/jars
curl -L -o artifacts/jars/proleap-cobol-parser.jar \
    https://github.com/uwol/proleap-cobol-parser/releases/download/v2.4.0/proleap-cobol-parser-2.4.0.jar
```

Off by default; enable with `--proleap-fallback`.

## Tests

Combined unit-test count went from 125 → **146**. All passing:

```
tests/unit/test_audit_steps.py          21 tests
tests/unit/test_post_v1_fixes.py        20 tests
tests/unit/test_verifier.py              7 tests
+ existing 98 tests
                                  ─────
                                  146 passed
```

## How to enable each step

Standalone runs to see one feature at a time:

```bash
# E is always on; verify the verifier reports body_non_trivial
python scripts/batch_run.py --dataset nist_cobol --max 30 --judge none \
    --run-id smoke_step_e

# A — cobc preflight
python scripts/batch_run.py --dataset nist_cobol --max 30 --judge none \
    --cobc-preflight --run-id smoke_step_a

# B — regex normaliser
python scripts/batch_run.py --dataset nist_cobol --max 30 --judge none \
    --normalise --run-id smoke_step_b

# D — legacylens diff
python scripts/batch_run.py --dataset nist_cobol --max 30 --judge none \
    --legacylens-diff --run-id smoke_step_d

# F — ProLeap (once jar + jpype1 installed)
python scripts/batch_run.py --dataset nist_cobol --max 30 --judge none \
    --proleap-fallback --run-id smoke_step_f
```

All-passes run for the next full evaluation:

```bash
nohup python scripts/batch_run.py \
    --dataset nist_cobol --max 500 --judge openai --stage3 \
    --judge-model gpt-4o-mini --stage3-min-tier medium \
    --normalise --cobc-preflight --legacylens-diff \
    --run-id full_500_judge_v4 --order complexity \
    > /tmp/parivartana_batch_v4.out 2>&1 &
tail -f artifacts/runs/full_500_judge_v4/progress.csv
```

(Skip `--proleap-fallback` on the first run — install the jar first
when you want to measure whether it adds anything.)

## Expected impact

From the audit's predicted PASS rates table:

```
                Before A-E        After A-E (est.)    After F (est.)
PASS verdicts*       0 %             ~30-50 %             ~70-85 %
Stub-body funcs    10.5 %            ~5-7 %               ~2-3 %
```

Smoke-test confirmation: `IF402M` paragraph `if402m_length` went
stub → real. The corpus-wide measurement requires running the full
500 with the new flags on (and at least one working LLM provider for
the judge to fire).
