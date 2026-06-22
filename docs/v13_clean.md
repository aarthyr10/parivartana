# v13 (clean) — rebuilt on v12, hacks removed

After the v14 oracle run collapsed to ~2% on the real LLM judge, we
established that the no-crash metric (python_smoke) had been driving the
code in the wrong direction: the hacks that boosted "doesn't crash" made
the generated Python *hackier*, which the judge penalises. This v13 keeps
only v12's genuine quality wins and adds clean improvements.

## What was better in v12 (kept)
- **Figurative constants** — `SPACE→' '`, `ZERO→0`, `QUOTE`, `HIGH/LOW-VALUE`,
  `NULL` resolve to real values (was `NameError: space`). Correct + clean.
- **Bare-PIC decoding** — `999`/`9`/`X(80)` masks decode properly, so
  numeric fields default to `0`, not `''`. Correct + clean.
- Clean, readable generated code: plain `state['b'] = state['b'] + state['a']`,
  real `def paragraph()` functions, a module docstring on every program.

## Reverted from v13/v14 (the hacks that hurt the judge)
| Removed | Why |
|---|---|
| `(x or 0)` wrapping on every arithmetic operand | clutters code; judge penalises readability/pythonic |
| `def NAME(): pass` stubs for undefined paragraphs | empty stubs read as broken/incorrect |
| `open(name,'a').close()` file touches before OPEN | hacky side-effect, not faithful |
| `READ` raising `EOFError` on empty + forced wrap | contorted control flow |
| `ACCEPT` try/except → `''` | reverted to clean `input()` |
| `_IO_VERBS_NEEDING_ENV = set()` | restored v12's narrowed skip set |

## Clean improvements added in this v13 (over v12)
1. **DISPLAY concatenation correctness.** COBOL `DISPLAY A B` concatenates
   with no separator; v12 emitted `print(a, b)` which inserts spaces
   (wrong output). Now `print(a, b, sep="")` — matches COBOL and is
   pythonic. A genuine correctness win the judge should reward.
2. **Clean no-PIC default.** Group/no-PIC items default to `0` (was
   `None`), so arithmetic stays plain `a + b` without the `(x or 0)`
   clutter and without `NoneType` crashes.

## Infra kept (unrelated to the hacks)
- `--judge-model` defaults to **gpt-4o-mini** + judge inputs truncated to
  6 KB (the v14 speed fix — minutes, not hours).
- `--stage2` defaults to **rule** (neural needs a fine-tuned checkpoint).

## Status
- Sandbox python_smoke (no-crash): 277 PASS / 175 STRUCTURAL / 7 FAIL.
- 148 unit+integration tests pass.
- **The real metric (LLM judge) can only be measured on your Mac.** This
  v13 is cleaner than both v12 (DISPLAY fix) and old-v13/v14 (no hacks),
  so it should judge at least as well as v12 and likely better. Verify:

```
python scripts/batch_run.py --dataset nist_cobol --max 2000 \
    --judge openai --judge-model gpt-4o-mini --run-id v13_clean_oracle
```

Compare the **mean llm_judge correctness score** against v12, not the
0.70-binary pass rate. For NIST, `execution_match` can't run (CCVS
harness programs don't execute standalone), so the judge score
distribution is the honest success metric.

## Stale files to delete locally (sandbox couldn't remove)
- docs: `v13_arithmetic_coercion.md`, `v14_io_handling.md`,
  `v14_oracle_diagnosis.md`, `v13_deep_analysis.md`
- run dirs under `artifacts/runs/`: `v14_deep`, `full_v14_nist`,
  `v13_deep`, `v12_neural`, `v12_postclean`, and the old `full_500_judge_v1*`
  sweep dirs.
