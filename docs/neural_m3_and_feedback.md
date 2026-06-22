# Neural on Apple M3 Pro (D) + professor feedback (F)

## D — Run / fine-tune CodeT5+ on Apple M3 Pro (36 GB)

Apple Silicon GPUs are supported by PyTorch via the **MPS** backend, and
`NeuralTranslator._resolve_device()` already returns `"mps"` when
available — so no code change is needed to use the M3 Pro GPU. 36 GB
unified memory is comfortable for `codet5p-220m` (220 M params)
fine-tuning and inference.

### 1. Install torch + the HF stack (in your venv)
```
pip install --upgrade torch transformers accelerate datasets sentencepiece safetensors
python -c "import torch; print('MPS available:', torch.backends.mps.is_available())"
```
Expect `MPS available: True`.

### 2. Inference (only useful with a fine-tuned checkpoint)
The base `Salesforce/codet5p-220m` is NOT trained for COBOL→Python and
produces unusable output (that was the v14 catastrophe). `--stage2
neural` is guarded: with no checkpoint at `--checkpoint-dir` it falls
back to rule-based. Once you have a fine-tuned checkpoint:
```
python scripts/batch_run.py --dataset nist_cobol --max 2000 \
    --stage2 neural --checkpoint-dir artifacts/checkpoints/codet5p_cobol \
    --judge openai --judge-model gpt-4o-mini --run-id v_neural
```

### 3. Fine-tune (the proposal's core ML deliverable)
The curriculum trainer exists: `src/pipeline/stage2_neural/training.py`
(`CurriculumTrainer`, easy→hard tiering). It already includes an MPS
cache-clear callback, so it's M-series aware.
- Validate the scheduler without training:
  `python -m src.pipeline.stage2_neural.training --dry-run`
- Full training needs a **parallel COBOL→Python dataset** of
  `ParallelExample(source_prompt, target_python, tier)`. That dataset
  does not exist yet — building it is the prerequisite (options: mine
  NIST/IBM with the rule-based+refined output as targets, or warm-start
  from CodeXGLUE Java→Python transfer). Then call
  `CurriculumTrainer(cfg).train(examples)`.
- On M3 Pro: use a small per-device batch (4–8), `fp16`/`bf16` off (MPS
  prefers fp32 for stability), gradient accumulation for effective batch.

Tip: tokenizer loading on transformers 5.x is already handled by the
robust loader in `translator.py`.

## F — Professor feedback status

### Done in code
- ANTLR4 fully removed (requirements, `configs/models.yaml`, Settings page).
- Parser-free Stage 1; CodeT5+ wired (opt-in, checkpoint-guarded).
- Dataset scope cut to P0 (NIST/IBM/CodeXGLUE/FEVER).

### Still open
1. **CMOS on the proposal document** (not in this repo — the uploaded
   PDF). Checklist to apply:
   - In-text citations → Chicago author-date: `(Challa et al. 2025)`,
     `(Rozière et al. 2020)` — no comma, no venue inside the parenthesis.
   - Fix the dataset-count discrepancy (stated ~285k vs the nine listed
     summing to ~462k).
   - Fix the novelty list numbering (three unnumbered bullets + a stray
     "(4)").
   - GPT-4 → "a frontier LLM (e.g. GPT-4-class / Claude)".
2. **Narrative refocus** (per feedback): present the rule-based stage as
   the deterministic *draft*, and the **neural translation + LLM
   refinement** as the quality layer — that's where correctness/idiom
   gains come from. The README has been updated to say this.

## Honest note
The rule-based translator alone is judged ~0.62 correctness / 0.52
pythonic (caps ~0.66 weighted vs the 0.70 gate). The neural model (D)
and the improved Stage-3 refiner (C) are the real levers to cross it;
the opt-in flags A/B let you test cheaper rule-based gains first.
