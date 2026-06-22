# Improvement backlog — analysis & ideas (not implemented)

Baseline: code reverted to **v12** (figurative-constant fix + bare-PIC
decoding). Kept only non-translation infra that strictly helps: the
judge speed fix (gpt-4o-mini + 6 KB truncation) and `--stage2` defaulting
to `rule`. Everything else post-v12 was reverted as non-improving.

## Why the judge caps ~0.66 weighted (the evidence)
From the real LLM-judge run (`full_v13_nist_final`, 459 progs, 32.7%
pass): correctness **0.62**, pythonic_idioms **0.52**, readability 0.66,
pep8 0.82, types 0.80. Two structural causes, both visible in the code:

- **Incomplete control flow.** Entry paragraph often renders as an empty
  `def x(): return`, so the real-logic paragraphs are never called
  (example: `SG401M`). Judge → "lacks functional behavior."
- **Un-pythonic state.** Everything is `state['x']` dict access. Judge →
  low pythonic_idioms.

`execution_match` can't run on NIST (CCVS harness programs exit rc=1 under
GnuCOBOL standalone), so the LLM judge is the only correctness oracle for
that dataset.

## Improvements, prioritized

### A. Translation correctness (raise the 0.62)
1. **Fix entrypoint control flow.** When the chosen entry paragraph has a
   trivial body (only `return`/`pass`) or doesn't `PERFORM` the others,
   fall through to subsequent paragraphs in source order (COBOL
   semantics). Highest single lever. Risk: double-execution for
   PERFORM-driven programs — must guard and validate on a judge run.
2. **Model PERFORM properly.** `PERFORM A THRU B`, `PERFORM ... VARYING`,
   section-level PERFORM, and inline PERFORM ranges. Many paragraphs are
   currently isolated functions with no caller.
3. **Implement stubbed verbs.** INSPECT, STRING/UNSTRING, EVALUATE,
   SEARCH, SET, nested IF/ELSE — anything emitting `pass` leaves an empty
   body the judge penalises.

### B. Pythonic idioms (raise the 0.52)
4. **Replace the `state[...]` dict** with real local variables or a
   `dataclass`/`SimpleNamespace` per program, so generated code reads like
   hand-written Python.
5. **Idiomatic constructs:** real `for`/`while` from PERFORM VARYING/UNTIL,
   f-strings for DISPLAY, list/dict comprehensions where natural.

### C. Stage-3 LLM refinement (the proposal's designed quality lever)
6. **Verify Stage-3 actually runs and lifts the judged score.** Measure
   judge(refined) − judge(raw). If the delta is ~0, the refiner prompt is
   the problem.
7. **Improve the refiner prompt:** give it the COBOL + rule-based draft and
   ask for a faithful, idiomatic, fully-implemented rewrite (no stubs,
   real variables). This directly targets correctness + pythonic, the two
   weak dimensions.

### D. Neural model (the proposal's ML contribution)
8. **Fine-tune CodeT5+** on the curriculum (NIST/IBM, easy→hard) to produce
   a real checkpoint, so `--stage2 neural` adds value. Needs torch + GPU.
9. **Build the parallel COBOL→Python training set** (currently missing) —
   e.g., rule-based+refined pairs, or CodeXGLUE transfer as warm-up.

### E. Evaluation & hygiene
10. **Report the judge score distribution** (mean correctness), not the
    0.70 binary, for NIST — `execution_match` is unavailable there.
11. **Add a small self-contained executable COBOL eval set** (non-CCVS) so
    `execution_match` gives a true behavioural signal.
12. **Reweight / reconsider the 0.70 threshold** — a reporting decision,
    not a translation fix; be explicit if changed.
13. **Run-artifact hygiene:** use a unique `--run-id` per run. The export
    showed contaminated dirs (816, 1836, 2285 traces in a 459-program
    dataset) from re-running the same id.

### F. Professor feedback still open
14. **CMOS on the proposal document** — in-text citations to author-date
    `(Author Year)`, fix the dataset-count discrepancy, fix novelty
    numbering. Not code; still outstanding.
15. **Narrative refocus on neural + LLM refinement** — per the feedback;
    today the rule-based translator carries everything.

## Recommended order
A1 (entrypoint control flow) → C6/C7 (verify + improve Stage-3 refinement)
→ B4 (state model) → D8 (fine-tune). A1 and C7 are the two that most
directly move correctness and pythonic, the dimensions gating the judge.
