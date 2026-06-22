# v17–v18 — Surfacing and fixing masked failures

Continues the v11–v16 sweep. Two cumulative fixes, each verified by a
full NIST 500 run (offline, `--judge none`; behavioural signal =
`python_smoke` only).

## Result comparison

| Run | Change | Behav. PASS | STRUCTURAL | FAIL | Headline |
|-----|--------|------------:|-----------:|-----:|---------:|
| v11 | consolidated baseline (old blanket I/O skip) | 53 (11.5%) | 406 | 0 | 100% |
| v17 | run output-only programs in scratch dir + empty stdin | 77 (16.8%) | 175 | 207 | 54.9% |
| v18 | + figurative-constant fix | 78 (17.0%) | 175 | 206 | 55.1% |

The headline *drop* from 100% to ~55% is the point: v11's 100% was an
illusion — 406 file-I/O programs were never executed, just marked
STRUCTURAL_PASS. v17 actually runs them, which converts the untested
population into 77 real PASSes and **207 genuine FAILs that were always
broken but hidden**.

## Fix 1 (v17) — stop blanket-skipping file-I/O in `python_smoke`

`src/evaluation/verifier.py`

- Narrowed `_IO_VERBS_NEEDING_ENV` from
  `{OPEN, READ, WRITE, REWRITE, DELETE, START, CLOSE, ACCEPT}` to
  `{READ, REWRITE, DELETE, START, ACCEPT}`. Only verbs that consume
  *external input* force a skip. Output-only programs
  (`OPEN OUTPUT` / `WRITE` / `CLOSE`) are no longer skipped.
- `_check_python_smoke` now runs the script in a throwaway scratch
  directory (`cwd=`) with `stdin=DEVNULL`, so output files land in
  scratch and stray input reads can't hang the run.

This mirrors the v8 rollback that removed blanket file-I/O skipping
from the *execution* check — the same reasoning was never applied to
`python_smoke` until now.

## Fix 2 (v18) — figurative constants resolve to real values

`src/pipeline/stage2_neural/rule_based.py`

Root cause of the largest failure class: `MOVE SPACES TO X` compiled to
`state['x'] = space`, crashing with `NameError: name 'space'`.
**185 of v17's 207 FAILs were this one bug.**

- `_operand()` now maps figurative constants:
  `SPACE/SPACES → ' '`, `ZERO/ZEROS/ZEROES → 0`,
  `QUOTE/QUOTES → '"'`, `HIGH-VALUE(S)/LOW-VALUE(S)/NULL(S) → ''`
  (mirrors the VALUE-clause handler in `_default_for_value`).
- `_is_literal()` extended to the full figurative set so HIGH/LOW-VALUE,
  QUOTE and NULL route through `_operand` instead of becoming undefined
  `state[...]` lookups.

Verified: `NameError: name 'space'` went from 185 → 0.

## Why PASS barely moved (77 → 78) and what's next

`space` was the *first* exception each program hit; fixing it lets those
programs run further, where they now hit the **next** masked bug:

```
199  TypeError: can only concatenate str (not "int") to str
  6  NameError (ccvs1, head_routine — undeclared NIST cross-module refs)
  1  FileNotFoundError
```

So v18 traded 185 `NameError`s for 199 `TypeError`s — the fix is
correct and a prerequisite, it just unmasked the layer beneath it.

**Next iteration target:** the str+int `TypeError`. Numeric operands are
being rendered into string-concatenation contexts (DISPLAY / STRING /
output-line building) without coercion. Candidate fix: wrap operands in
`str()` when building display/string output, or carry PIC type through
so numeric and alphanumeric fields concatenate consistently. Hold for
the next run so the delta stays attributable.

## Carried forward

Both fixes are now baseline. The conservative pre-v17 skip can be
restored by re-adding the output verbs to `_IO_VERBS_NEEDING_ENV` if a
behaviour-only (non-surfacing) headline is ever wanted.
