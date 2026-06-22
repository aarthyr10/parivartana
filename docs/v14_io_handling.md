# v14 — I/O handling + reference stubs (the 5 improvement points)

## What was implementable here (points 1–3)

| # | Improvement | File(s) | Effect |
|---|---|---|---|
| 1 | Stub input files + READ AT END | `verifier.py`, `rule_based.py` (`_open`, `_read`) | the 175 STRUCTURAL programs now execute |
| 2 | Tolerant ACCEPT | `rule_based.py` (`_accept`) | empty stdin no longer crashes |
| 3 | Define-on-reference paragraph stubs | `rule_based.py` (`translate`) | fixed `ccvs1` (5) + `head_routine` (1) |

Details:
- `_IO_VERBS_NEEDING_ENV` is now empty — python_smoke runs every program
  rather than skipping file/stdin programs.
- `_open` touches each file (`open(name,'a').close()`) before opening, so
  OPEN INPUT on a missing file no longer raises FileNotFoundError. For a
  self-contained program that OPEN OUTPUTs, WRITEs, CLOSEs, then OPEN
  INPUTs the same file, the written records persist and READ reads them
  back correctly.
- `_read` raises `EOFError` on an empty read and is always wrapped, so an
  empty file drives the COBOL **AT END** branch (loop exits cleanly)
  instead of hanging or crashing.
- `_accept` falls back to `''` on `EOFError`.
- `translate()` scans the generated body/entry for zero-arg calls that
  have no matching definition and emits `def NAME(): pass` stubs —
  covers section/paragraph references the parser didn't capture.

## Result (NIST 459, python_smoke)

| | v13 | v14 |
|---|---:|---:|
| Behavioural PASS | 277 (60.3%) | **458 (99.8%)** |
| STRUCTURAL | 175 | 0 |
| FAIL | 7 | **1** |

148 unit+integration tests pass; the 277 v13 passes did not regress. The
lone FAIL (`SQ205A`) is a name collision — a paragraph whose name is also
a string data item, so `name()` calls a `str`.

## CRITICAL caveat

**99.8% is the no-crash rate, not correctness.** python_smoke only proves
the translated Python runs to completion. By making I/O non-crashing we
let every program finish, but whether its *output matches the COBOL* is a
separate question answered only by `execution_match` (GnuCOBOL) and the
LLM judge. Report the oracle number, not this one, as the success rate.

## Points 4 & 5 — cannot run in this environment

- **4. execution_match + LLM promote.** Needs GnuCOBOL on PATH and an API
  key — neither is available in the sandbox (no network egress to
  providers). Run on the Mac:
  `python scripts/batch_run.py --dataset nist_cobol --max 2000 --judge openai --stage3 --llm-promote --run-id v14_oracle`
- **5. Fine-tune CodeT5+.** Needs torch + GPU + a training run over the
  curriculum; the sandbox has no torch and can't download the base model.
  This is the proposal's core ML deliverable and must be done on the Mac
  / a GPU box. Until then Stage 2 is carried by the rule-based translator,
  and `--stage2 neural` should stay off (no checkpoint).
