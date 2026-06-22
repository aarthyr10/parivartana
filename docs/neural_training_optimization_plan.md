# Neural training: add, optimize, and visualize (the ML deliverable)

This is the plan to turn Stage-2 from "a checkpoint that loses to the rule
baseline" into the proposal's real ML contribution, plus the academic figures
the professor asked for. It supersedes the data section of
`neural_training_plan.md` with what we learned from the first verified run.

## Two findings that reshape the plan

**1. Execution-verified COBOL→Python data is scarce.** The first verified build
(`artifacts/training_data/verified/build_stats.json`) processed 120 candidates
and kept **7** (all 7 verified). Breakdown: 95 `skip_cobol_rc` (the COBOL does
not run standalone — NIST CCVS harness programs), 10 `skip_mismatch`, 1 COBOL
timeout, 7 LLM timeouts; 84 minutes wall-clock. Seven pairs cannot train a 220M
model. Data volume is now the primary problem.

**2. The "Java→Python transfer corpus" is actually Java→C#.** The local
`data/raw/codexglue/` is the CodeXGLUE **code-to-code (Java→C#)** task: all
10,300 train pairs are `src_lang=java, tgt_lang=cs`, with C# targets. It cannot
warm-start a *Python* decoder. The proposal's "CodeXGLUE Java→Python (110k)"
line should be corrected, and the warm-start source changed (below).

## Strategy: make the small COBOL set enough by warming the model first

The model needs two things it can't get from 7 COBOL pairs: (a) fluent **Python
generation**, and (b) **COBOL→Python adaptation**. We supply each from a
different source and join them with the curriculum.

### A. Data volume

| Source | Type | Role | How |
|---|---|---|---|
| `--keep-unverified` (new) | **silver** COBOL→Python (LLM target, not exec-checked) | bulk adaptation signal, early tiers | recovers the 95+10 skipped programs in one pass, tagged `verified=false` |
| execution filter | **gold** COBOL→Python | high-confidence, later tiers + eval | `--execution-filter` keeps only stdout-matching pairs |
| Forward synthesis (roadmap) | gold, self-contained | scales runnable COBOL arbitrarily | Python(HumanEval/MBPP)+tests → teacher Python→COBOL → keep COBOL passing tests under GnuCOBOL → invert pair |
| COBOLEval (roadmap) | gold, 146 runnable | clean held-out eval + a few train pairs | port the 146 COBOL problems + canonical HumanEval Python |
| CoSQA+CodeSearchNet (present, P2) | NL→Python | **Python-decoder warm-start** (replaces the Java→C# corpus) | docstring→Python pretraining so the decoder emits real Python |

The immediate, free win is `--keep-unverified`: it converts the 84-minute run
that produced 7 pairs into ~110 tagged pairs (gold where the COBOL ran, silver
elsewhere) from the **same** candidates. Silver is noisy (teacher output, not
verified) so it is used only in the SIMPLE/MEDIUM tiers; gold carries HIGH and
all evaluation.

### B. Optimized two-phase training

Implemented in `src/pipeline/stage2_neural/training.py` (new flags
`--init-from`, `--peft lora`, `--epochs`, `--batch-size`, `--lr`, `--backbone`):

1. **Phase 1 — Python warm-start.** Fine-tune `codet5p-220m` on NL→Python
   (CodeSearchNet) so the decoder is fluent in Python before it ever sees COBOL.
   Saves to `artifacts/checkpoints/codet5p_py`.
2. **Phase 2 — COBOL curriculum.** Continue from Phase 1 (`--init-from`), running
   the existing `CurriculumScheduler` over gold+silver tiers (SIMPLE→MEDIUM→HIGH,
   released on validation plateau). Saves to `artifacts/checkpoints/codet5p_cobol`.

Optimizations now available:
- **LoRA / PEFT** (`--peft lora`): trains ~0.5–2% of params, fits the M3 Pro
  comfortably, much faster epochs, and avoids catastrophic forgetting of the
  Phase-1 Python fluency. Requires `pip install peft`.
- **MPS profile** (already in `run()`): per-device batch 1 + grad-accum, seq-len
  caps, gradient checkpointing — kept.
- **Early stopping** + `load_best_model_at_end` — kept.
- **Backbone scaling**: `--backbone Salesforce/codet5p-770m` if memory allows,
  for HIGH-tier programs.

### C. Honest evaluation
Score the neural checkpoint the same way as the rule baseline, on the same
programs: `execution_match` where COBOL runs, LLM judge elsewhere, CodeBLEU as a
secondary signal. The bar: **neural must beat rule on judge correctness/pythonic**
(the 0.62/0.52 dimensions gating 0.70), not merely run. Use a fresh `--run-id`.

## Commands (run on the Mac with the venv active)

```bash
# 0. deps
pip install peft torchview          # torchview only needed for the forward-graph figure
brew install graphviz               # to render the .dot figures to SVG/PNG

# 1. DATA — recover gold+silver in one pass (start local+free; --workers for speed)
export LOCAL_LLM_BASE_URL=http://localhost:11434/v1
python scripts/build_training_data.py \
    --datasets ibm_open_cobol nist_cobol \
    --targets llm --provider ollama --teacher-model qwen2.5-coder:7b \
    --execution-filter --keep-unverified --timeout 10 --workers 4 \
    --out artifacts/training_data/cobol_mix
#   -> train.jsonl/val.jsonl with `verified` true(gold)/false(silver); watch the log.

# 2a. PHASE 1 — Python-decoder warm-start (build a NL->Python set first, then train)
#     (build_transfer_data is the roadmap script; until then, warm-start is optional)
python -m src.pipeline.stage2_neural.training --config configs/models.yaml \
    --train artifacts/training_data/py_warm/train.jsonl \
    --val   artifacts/training_data/py_warm/val.jsonl \
    --peft lora --epochs 3 --output-dir artifacts/checkpoints/codet5p_py

# 2b. PHASE 2 — COBOL curriculum, continuing from Phase 1
python -m src.pipeline.stage2_neural.training --config configs/models.yaml \
    --train artifacts/training_data/cobol_mix/train.jsonl \
    --val   artifacts/training_data/cobol_mix/val.jsonl \
    --init-from artifacts/checkpoints/codet5p_py \
    --peft lora --epochs 20 --output-dir artifacts/checkpoints/codet5p_cobol

# 3. EVALUATE neural vs rule on the same programs
python scripts/batch_run.py --dataset nist_cobol --max 2000 --stage2 neural \
    --checkpoint-dir artifacts/checkpoints/codet5p_cobol \
    --judge openai --judge-model gpt-4o-mini --stage3 --run-id neural_eval
python scripts/batch_run.py --dataset nist_cobol --max 2000 --stage2 rule \
    --judge openai --judge-model gpt-4o-mini --stage3 --run-id rule_eval
```

If the local teacher is too slow, swap `--provider openai --teacher-model gpt-4o`
in step 1, or skip Phase 1 and train Phase 2 from the base backbone directly.
Validate the loop with no GPU at all via `python -m
src.pipeline.stage2_neural.training --dry-run`.

## Academic figures — `scripts/visualize_model.py`

Emits Graphviz `.dot` (+ `.svg`/`.png` when `dot` is installed) to `docs/figures/`.

```bash
python scripts/visualize_model.py --which all \
    --checkpoint artifacts/checkpoints/codet5p_cobol --out-dir docs/figures
```

| Figure | File | Needs torch? | Shows |
|---|---|---|---|
| Model layer/module tree | `model_module_tree.{dot,svg,txt}` | yes (Mac) | CodeT5+ encoder-decoder module hierarchy with per-module param counts |
| Forward computation graph | `forward_graph.svg` | yes + torchview (Mac) | tensor data-flow through the network on a sample input |
| Curriculum tree | `curriculum_tree.{dot,svg,png}` | no | the two-dimensional curriculum (similarity × tier), gold/silver split |
| AST→neural pipeline | `ast_neural_pipeline.{dot,svg,png}` | no | a real parsed COBOL AST → prompt → CodeT5+ → Python |

The two torch-free figures are already generated and checked in under
`docs/figures/`. The two model figures need the Mac venv (the script prints a
clear "run on the Mac" message and skips cleanly elsewhere).

## Where this leaves us
- The neural model becomes trainable tonight (silver+gold via one flag) and
  optimized (LoRA + two-phase warm-start), instead of blocked on 7 examples.
- Evaluation is apples-to-apples against the rule baseline on the same oracle.
- The professor gets four publication-ready figures from one command, two of
  which are already produced.

## Honest caveats
- Silver pairs are unverified teacher output; treat the silver-trained model as a
  step, and report gold-only and gold+silver results separately.
- Real GPU training runs on the M3 Pro, not in the offline sandbox; everything
  here is validated up to the GPU step (imports, curriculum dry-run, figures).
- Forward-synthesis and COBOLEval ingestion are specified here but not yet coded;
  they are the next data-volume lever if silver+gold is insufficient.
