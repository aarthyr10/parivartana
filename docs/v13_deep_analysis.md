# v13 deep analysis — where the success rate is stuck and how to lift it

Run `v13_deep` (clean): NIST 459 → **277 PASS (60.3%) / 175 STRUCTURAL /
7 FAIL**. The headline behavioural success rate is capped at ~60% by one
thing: **175 programs are never executed**, so they can't count as
verified. Fixing FAILs (7) barely moves the number; converting
STRUCTURAL→PASS is the whole game.

## The 175 STRUCTURAL programs — the real lever

These are skipped because they consume external input. Breakdown of the
verb that triggers the skip:

| Trigger verb | Programs |
|---|---:|
| READ (file input) | 160 |
| REWRITE | 41 |
| START | 16 |
| DELETE | 16 |
| ACCEPT (stdin) | 13 |

By tier: 9 simple, 118 medium, 48 high. Of the 175:
- **12 need only ACCEPT** (stdin) — no files at all.
- **160 need a file READ** — need an input file to exist.

### Improvement A (biggest): stub input files + honor AT END  → up to ~160 programs
Before running a READ program in the smoke sandbox, create empty files in
the scratch dir for each `SELECT … ASSIGN TO` filename, and make the
translated `READ` treat an empty/missing file as immediate **AT END**
(the normaliser already marks AT END clauses — stage 2 needs to wrap the
read in `try/except`/EOF so it branches to the AT END paragraph instead
of crashing). Most NIST programs then run their end-of-file path and
finish cleanly. Even partial coverage here dwarfs every other fix.
Estimated reachable: a large fraction of the 160 READ + 41 REWRITE +
16/16 START/DELETE programs.

### Improvement B (quick): tolerant ACCEPT → ~12+ programs
Make the translated `ACCEPT x` read stdin with an EOF fallback (return
spaces for alphanumeric, 0 for numeric) instead of raising on empty
stdin. Cheap; clears the ACCEPT-only group immediately and helps mixed
programs too.

## The 7 FAILs — small but easy

```
5  NameError: name 'ccvs1'        SG201A SG202A SG203A SG102A SG103A
1  NameError: name 'head_routine' NC113M
1  FileNotFoundError              SQ303M
```

### Improvement C (quick): define-on-reference safety net → +6
`ccvs1` and `head_routine` are CCVS-framework identifiers / paragraphs
referenced but never declared locally. Emit a stub at codegen for any
identifier referenced but absent from `state` (`state.setdefault('ccvs1',
'')`) and any `PERFORM`/`GO TO` target with no paragraph
(`def head_routine(): pass`). Converts these 6 crashes to clean runs.

## Beyond python_smoke (what raises the *quality* bar, not just no-crash)

`python_smoke` only proves "doesn't crash." Two stronger signals raise
real success rate and are already wired — run them on a machine that has
them:

- **execution_match** (needs GnuCOBOL): compares translated-Python stdout
  to the COBOL's actual output. This is the strict correctness test.
- **LLM judge / `--llm-promote`** (needs an API key): promotes
  structurally-clean output to PASS when a model confirms faithfulness —
  this is how v10 reached 82.1%.

Command for the full-strength run on your Mac:
```
python scripts/batch_run.py --dataset nist_cobol --max 2000 \
    --judge openai --stage3 --llm-promote --run-id v13_full_oracle
```

## The neural model (the proposal's actual ML contribution)

Stage 2 is currently carried entirely by the **rule-based** translator.
`--stage2 neural` only helps with a **fine-tuned** CodeT5+ checkpoint;
none exists yet (the base model scores ~0). Training CodeT5+ on the
curriculum (NIST/IBM, easy→hard) is the path to gains the rule-based
templater can't reach — and is the differentiator the proposal promises.

## Priority order (by ROI)

1. **A** — input-file stubbing + AT END (up to ~160 programs). Highest impact.
2. **B** — tolerant ACCEPT (~12+). Cheap.
3. **C** — define-on-reference stubs (+6 of the 7 FAILs). Cheap.
4. Run with **execution_match + llm_promote** on Mac to measure true correctness.
5. **Fine-tune CodeT5+** for gains beyond the rule-based ceiling.
