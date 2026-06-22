# v12 — Verified-correct climb over v11

Direction change: instead of measuring a 100% headline that mostly
counts *un-tested* programs, v12 actually executes the file-I/O
programs and reports real behavioural PASS. The headline drops below
100% on purpose — the number that matters (verified-correct
translations) more than quadruples.

## v11 → v12

| Metric | v11 | v12 | Δ |
|---|---:|---:|---:|
| Behavioural PASS (executed & clean) | 53 (11.5%) | **266 (58.0%)** | **+213** |
| STRUCTURAL_PASS (skipped, untested) | 406 | 175 | −231 |
| FAIL (executed & broken) | 0* | 18 (3.9%) | +18 |
| Headline (PASS+STRUCTURAL) | 100% | 96.1% | −3.9pp |

\* v11's 0 FAIL was an artefact of skipping every file-I/O program, not
of correctness. Those programs were never run.

**Read this as:** verified-correct translations went 53 → 266. The 18
FAILs are real bugs that were previously invisible.

## Three fixes stacked into v12

1. **Execute output-only I/O programs** (`verifier.py`). `python_smoke`
   now skips only programs that consume external input
   (READ/REWRITE/DELETE/START/ACCEPT); OPEN/CLOSE/WRITE programs run in
   a throwaway scratch dir with empty stdin. This is what exposes real
   behaviour instead of rubber-stamping STRUCTURAL_PASS.
2. **Figurative constants** (`rule_based.py`). `MOVE SPACES TO X` no
   longer emits `state['x'] = space` (NameError). SPACE→`' '`,
   ZERO→`0`, QUOTE→`'"'`, HIGH/LOW-VALUE/NULL→`''`. Routed through
   `_operand`/`_is_literal`.
3. **Bare PIC mask decoding** (`normaliser.py`) — the big lever. The
   AST stores PIC masks pre-stripped (`'999'`, `'9'`, `'X(80)'`), but
   `_PIC_RE` required the literal `PIC` keyword, so every bare numeric
   mask failed to decode and `VALUE ZERO` fell through to `''` — which
   then crashed in arithmetic (`str + int`). Added an anchored
   `_BARE_PIC_RE` fallback. Now `999 → int/0`, `S9(4)V99 → Decimal`,
   `X(80) → " " * 80`. This single fix cleared the ~190-program
   `str + int` failure class.

## Remaining 18 FAILs (next targets)

```
11  TypeError: unsupported operand for +: 'NoneType'
     -> group / no-PIC items default to None, then used in arithmetic.
        Fix: give group items a numeric-or-string default by context,
        or coerce in _arithmetic.
 5  NameError: name 'ccvs1'
     -> CCVS-framework cross-module identifier never declared locally.
 1  FileNotFoundError  (an output path edge case)
 1  NameError: name 'head_routine'  (paragraph referenced, not emitted)
```

All three v12 fixes are carried forward as baseline.
