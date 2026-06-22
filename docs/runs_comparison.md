# Runs comparison (with file counts)

Authoritative end-of-run totals (the shared `artifacts/runs/` folders are
contaminated by repeated/overlaid runs, so these come from each run's
logged summary, not a re-read of `summary.csv`).

`Files` = programs scored (NIST is 459 complete programs after the 41
copybook fragments are excluded; the raw NIST dir holds ~510 files).

| Run | Dataset | Files | Behav. PASS | STRUCTURAL | FAIL | Headline | Notes |
|---|---|---:|---:|---:|---:|---:|---|
| v10 | NIST | 459 | 128 (27.9%) | 249 | 82 | 82.1% | Mac run *with* GnuCOBOL + LLM promote |
| v11 | NIST | 459 | 53 (11.5%) | 406 | 0 | 100%\* | structural baseline; \*inflated — I/O progs skipped, untested |
| v12 | NIST | 459 | 266 (58.0%) | 175 | 18 | 96.1% | figurative-constant + bare-PIC fixes; runs output-only I/O progs |
| v13 | NIST | 459 | 277 (60.3%) | 175 | 7 | 98.5% | + arithmetic coercion (`x or 0`); ANTLR4 fully removed |
| v13 | IBM | 129 | 78 (60.5%) | 41 | 10 | 92.2% | same code, IBM Open COBOL |
| **v13** | **NIST+IBM** | **588** | **355 (60.4%)** | **216** | **17 (2.9%)** | combined curated corpus |
| v14 | NIST | 459 | 458 (99.8%) | 0 | 1 | 99.8% | + input-file stubbing/AT END, tolerant ACCEPT, paragraph stubs |

> **v14 caveat — read carefully.** v14's 99.8% is the **python_smoke
> (no-crash) rate**, not a correctness rate. v14 makes file-I/O and ACCEPT
> non-crashing (touch input files, READ EOF→AT END, ACCEPT→`''`), so
> almost every program now runs to completion. That is a real prerequisite
> improvement, but "runs without crashing" is not "translates correctly."
> The honest correctness number requires `execution_match` (GnuCOBOL) and
> the LLM judge, which only run on the Mac:
> `python scripts/batch_run.py --dataset nist_cobol --max 2000 --judge openai --stage3 --llm-promote --run-id v14_oracle`

\* v11's 100% counts 406 file-I/O programs that were skipped (never
executed). v12/v13 actually run them, so their headline is lower but the
*verified-correct* count is ~5× higher.

Note: the user's first Mac run of v13 scored 1/459 because `--stage2`
had been defaulted to `neural`, loading the untrained base CodeT5+. That
default is reverted (now `rule`); the v13 numbers above are the
rule-based path.
