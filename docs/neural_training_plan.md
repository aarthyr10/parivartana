# Neural training plan — building real (non-circular) COBOL→Python data

## The problem in one sentence

Today the only parallel data we have pairs the linearised Stage-1 AST with the
**rule-based translator's own output** as the target (`scripts/build_training_data.py`,
`--targets rule`). A model trained on that can, at best, *imitate the rule-based
engine* — it can never exceed the baseline it is distilled from. The checkpoint
on disk (`codet5p-220m`, 447 train / 96 eval examples, 20 epochs) is exactly this
circular setup, which is why `--stage2 neural` does not beat `--stage2 rule`.

To make the neural model the real deliverable it needs **targets that are correct
independent of our rule engine**, and enough of them.

## What the literature actually does (and what we borrow)

| Work | Core idea | What we take |
|---|---|---|
| **MultiPL-T** — Cassano et al., OOPSLA 2024 | For a low-resource language, translate high-quality high-resource functions with an LLM and **keep only translations that pass unit tests**. Execution is the filter, not BLEU. | Our primary recipe: LLM-translate COBOL→Python, keep only pairs whose Python output **matches the COBOL output under GnuCOBOL**. |
| **TransCoder** — Rozière et al., NeurIPS 2020 | Unsupervised translation from *monolingual* code via back-translation; BLEU is the wrong metric, computational accuracy (tests passed) is right. | Optional Phase 4 to exploit monolingual COBOL (The Stack v2) once supervised data exists. Confirms execution-accuracy as the metric. |
| **Knowledge transfer / curriculum** — Cassano (above), Kühne et al. 2025 | Warm-start from a related high-resource pair; order examples easy→hard. | Phase 1 warm-start on CodeXGLUE Java→Python (already P0); the existing `CurriculumScheduler` orders by complexity tier. This is the proposal's promised *two-dimensional* curriculum (language similarity × AST complexity). |
| **COBOLEval** — BloopAI/zorse-project | 146 HumanEval problems hand-ported to COBOL, each with ~6 test cases, scored by compiling/running under GnuCOBOL. | A ready-made **executable** COBOL set with tests + canonical Python (from HumanEval) → cheap, high-confidence verified pairs and a clean held-out eval. |
| **COBOL-Coder** — Dau et al., 2026 | Compiler-guided validation + similarity filtering to curate COBOL training data; ships COBOL-JavaTrans. | The "compile first, then keep" discipline; a Java pivot (COBOL→Java→Python) as a fallback source of pairs. |
| **XMainframe / Mainframe-Instruct** — FPT, 2024 | Public COBOL base+instruct model and benchmark. | Optional stronger *teacher* than a generic LLM for the distillation step; useful baseline to cite. |

The unifying principle from all of them: **never trust a generated target you
haven't executed.** That is the single change that breaks the circularity.

## The pipeline we will build (4 phases)

```
                 CodeXGLUE Java→Python            NIST + IBM COBOL (.cob)
                        │                                 │
            Phase 1: warm-start CodeT5+          Phase 2: LLM teacher translates
            (transfer pretraining)                COBOL→Python  (--targets llm)
                        │                                 │
                        │                         GnuCOBOL execution filter
                        │                         keep pair only if
                        │                         python_stdout == cobol_stdout
                        │                                 │
                        └───────────────┬─────────────────┘
                                        ▼
                       Phase 3: curriculum fine-tune (easy→hard tiers)
                                        ▼
                       Phase 4: evaluate neural vs rule baseline
                                (judge + execution_match)
```

### Phase 1 — Warm-start on Java→Python (transfer)
CodeXGLUE Java→Python is already a P0 dataset and Java is structurally the closest
high-resource language to COBOL. Fine-tune the base `codet5p-220m` on Java→Python
first so the model learns "imperative source → idiomatic Python" before it ever
sees COBOL. This is cheap (no GnuCOBOL, no API) and is the bottom rung of the
two-dimensional curriculum.

### Phase 2 — Build verified COBOL→Python pairs (the key step)
For every NIST/IBM program: ask a strong **teacher** LLM for a full Python
translation, then **compile+run the COBOL under GnuCOBOL and run the Python**, and
keep the pair **only if stdout matches**. This is MultiPL-T applied to COBOL. The
teacher can be a frontier API model (best quality) or a local
`qwen2.5-coder` / Llama via Ollama/vLLM (free, slower). The execution filter is
already implemented (`src/evaluation/execution.py`), and the builder now supports
`--targets llm --execution-filter` (see commands below).

Reality check: many NIST programs are CCVS *harness* programs that exit non-zero
standalone, so they won't pass the execution filter — that is fine and expected.
The filter deliberately yields a smaller, high-confidence corpus. To grow it:
- add **COBOLEval** (146 self-contained, test-backed COBOL problems) — these run
  cleanly and pair to canonical HumanEval Python;
- add **forward synthesis**: take Python (HumanEval/MBPP) with tests, translate
  Python→COBOL, keep COBOL that passes the tests under GnuCOBOL, then invert the
  pair. This manufactures arbitrarily many runnable COBOL programs.

### Phase 3 — Curriculum fine-tune
Feed the union (Phase 1 warm-started weights + Phase 2 verified pairs) to the
existing `CurriculumTrainer`, which releases Simple→Medium→High tiers as the
validation metric plateaus (`src/pipeline/stage2_neural/curriculum.py`). On the
M3 Pro the MPS profile in `training.py` already handles batch/seq-len/checkpointing.

### Phase 4 — Honest evaluation
Run the held-out set through `--stage2 neural` and compare against
`--stage2 rule` on the **same** programs, using `execution_match` where the COBOL
runs and the LLM judge elsewhere. The neural model has to *beat the rule baseline
on the judge's correctness/pythonic dimensions* (the two that gate the 0.70 score),
not just run without crashing.

## Data-quality guardrails (from COBOL-Coder + MultiPL-T)
1. **Compile-gate the COBOL first** (`cobc -fsyntax-only`, already wired in
   `cobc_preflight.py`) so we never spend a teacher call on a broken program.
2. **Execution-filter the Python** (Phase 2) — the non-negotiable correctness gate.
3. **Deduplicate** near-identical NIST variants so the model doesn't overfit the
   CCVS boilerplate (similarity filter, COBOL-Coder style).
4. **Hold COBOLEval out entirely** as a clean test set — never train on it.
5. **Record provenance** (`target_source`, `verified` fields are now written per
   example) so a reviewer can see exactly which pairs are execution-verified.

## What this fixes vs. the current state
- Targets become correct independently of the rule engine → the model can exceed
  the baseline (breaks circularity).
- The curriculum becomes genuinely two-dimensional (Java→COBOL × tier), matching
  the proposal's stated novelty.
- Every training pair is execution-verified, which is also the proposal's own
  strictest metric — training and evaluation finally use the same notion of
  "correct."

## Risks / open items
- **Teacher cost.** Full NIST+IBM through a frontier API is a few hundred calls;
  start with `--max-per 50` and a local model to validate the loop for free.
- **Small verified yield on NIST.** Mitigated by COBOLEval + forward synthesis.
- **GnuCOBOL required** for Phase 2/4 — must run on the Mac (or any box with
  `cobc`), not the offline sandbox.
- **220M may be too small** for High-tier programs; `codet5p-770m` is the next
  step if the M3 Pro memory allows.
