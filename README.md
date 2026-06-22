# PARIVARTANA

> Sanskrit *parivartana* (परिवर्तन) — "transformation, conversion."

**A neural transpiler that converts legacy COBOL into idiomatic Python 3.**

Banks, insurance firms, and government offices still run on roughly 800 billion lines of COBOL. PARIVARTANA modernises this code through a three-stage AI pipeline: a thin COBOL preprocessor with complexity tiering, a curriculum-trained neural translator, and an LLM refinement layer with NLI semantic validation.

The rule-based templater is a fast, deterministic **draft**; the **neural translation (CodeT5+) and LLM refinement** are the quality layer that turns that draft into correct, idiomatic Python. Translation quality is measured by execution match (where the COBOL can run standalone) and an LLM-as-judge correctness score — not by "does it run without crashing."

## Pipeline

| Stage | Module | Status |
|---|---|---|
| 1. Preprocessor | `src.pipeline.stage1_parser` | **Production** — fixed-format stripping, recursive-descent parser over a ~25-verb subset, complexity tiering. Deliberately scoped as a preprocessor, not a full COBOL-85 grammar (see `docs/architecture.md` § Scope decisions). |
| 2. Neural | `src.pipeline.stage2_neural` | **Production** — CodeT5+ translator with tier-aware beam search, rule-based baseline + offline fallback, curriculum trainer. |
| 3. LLM | `src.pipeline.stage3_llm` | **Production** — provider adapters, dictionary-first rename, docstring synthesis, DeBERTa NLI semantic validator with lexical fallback. |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in OPENAI_API_KEY / ANTHROPIC_API_KEY / HUGGINGFACE_TOKEN
streamlit run app/Home.py
```

## Data & model downloads

To keep the repository lightweight, **datasets, trained models, checkpoints, run
outputs, and pipeline snapshots are not committed to git** (see `.gitignore`).
You download or regenerate them locally; the directory placeholders (`.gitkeep`
files) are tracked so the expected layout is preserved.

### Datasets

Every dataset is registered in `configs/datasets.yaml` with its canonical source
(a HuggingFace dataset repo, a GitHub repo, or the NIST FTP) under `source.url`.
Fetch the P0 (active) set with the ingest script, then place each corpus under
its matching `data/raw/<key>/` slot:

```bash
python scripts/ingest.py --list                # show priority + method per dataset
python scripts/ingest.py --all                 # download the P0 set (recommended)
python scripts/ingest.py --dataset codexglue   # download a single dataset
python scripts/ingest.py --status              # report local availability
```

| Key | Source | Store under |
|---|---|---|
| `nist_cobol` | NIST COBOL Test Suite (NIST FTP) | `data/raw/nist_cobol/` |
| `ibm_open_cobol` | IBM Open COBOL Samples (GitHub) | `data/raw/ibm_open_cobol/<domain>/` |
| `codexglue` | CodeXGLUE Java→Python (HuggingFace) | `data/raw/codexglue/` |
| `cobol_identifier_dict` | COBOL Identifier Dictionary | `data/raw/cobol_identifier_dict/` |
| `fever_nli` | FEVER NLI Corpus (HuggingFace) | `data/raw/fever_nli/` |
| `stack_v2_cobol` | The Stack v2 COBOL (HuggingFace, P2) | `data/raw/stack_v2_cobol/` |
| `cosqa_codesearchnet` | CoSQA + CodeSearchNet (HuggingFace, P2) | `data/raw/cosqa_codesearchnet/` |
| `swe_bench` | SWE-bench Python (HuggingFace, P2) | `data/raw/swe_bench/` |
| `gfg_multilingual` | GeeksForGeeks COBOL (scraped, P2) | `data/raw/gfg_multilingual/<algo>/` |

Per-file expectations for each slot are documented in `docs/datasets.md`.
Authenticated HuggingFace pulls require `HUGGINGFACE_TOKEN` in your `.env`.

### Models & checkpoints

Trained weights live under `artifacts/` and are also git-ignored. Obtain them in
one of two ways:

- **Train locally** — build the training data and run the curriculum trainer,
  which writes LoRA adapters and merged weights into
  `artifacts/checkpoints/codet5p_cobol/`:

  ```bash
  python scripts/build_training_data.py
  python scripts/merge_lora.py            # produce a merged inference checkpoint
  ```

- **Use a published checkpoint** — the base model (`Salesforce/codet5p-220m`) is
  pulled from HuggingFace on first run. Drop a fine-tuned PARIVARTANA checkpoint
  under `artifacts/checkpoints/codet5p_cobol/` (adapter) or
  `artifacts/checkpoints/codet5p_cobol_merged/` (merged). With no checkpoint
  present the pipeline falls back to the rule-based translator, so the app still
  runs end-to-end.

### Expected local layout (all git-ignored)

```
data/raw/<key>/             downloaded datasets
artifacts/checkpoints/      trained / fine-tuned model weights
artifacts/models/           exported inference models
artifacts/outputs/          generated translation batches
artifacts/training/         training run histories
```

## Dataset ingestion

Datasets are tagged `P0` (active, four datasets) or `P2` (deferred, four datasets) in `configs/datasets.yaml` after the P3 proposal scope cut. By default `--all` only pulls the P0 set; deferred adapters stay in the codebase and can be opted back in.

```bash
python scripts/ingest.py --dataset codexglue                # single dataset
python scripts/ingest.py --all                              # P0 only (recommended)
python scripts/ingest.py --all --include-deferred           # everything, including P2
python scripts/ingest.py --all --priority P0 --priority P1  # explicit priority filter
python scripts/ingest.py --status                           # local availability report
python scripts/ingest.py --list                             # show priority + method per dataset
```

**P0 (active, four datasets)** — NIST COBOL Test Suite (gold evaluation), IBM Open COBOL Samples (primary training), CodeXGLUE Java→Python (transfer pretraining), FEVER NLI Corpus (semantic validator). The COBOL Identifier Dictionary is also P0 and ships with the repo.

**P2 (deferred)** — The Stack v2 COBOL, CoSQA + CodeSearchNet, SWE-bench Python, GeeksForGeeks Multilingual. Ingestion adapters remain in `src/data/ingestion.py` but are skipped by default.

**Train vs. test split.** Each dataset is tagged TRAIN, TEST, or SUPPORT by its role in `configs/datasets.yaml` and surfaced in the Datasets → Overview tab.

| Use | Datasets |
|---|---|
| **TRAIN** — model learns from these | IBM Open COBOL (primary), CodeXGLUE Java→Python (transfer pretraining), FEVER NLI (semantic validator), The Stack v2 COBOL (encoder pretraining, P2), CoSQA + CodeSearchNet (docstring training, P2) |
| **TEST** — held out for evaluation | NIST COBOL Test Suite (gold), SWE-bench Python (execution accuracy, P2), GeeksForGeeks Multilingual (OOD, P2) |
| **SUPPORT** — auxiliary lookups, not learned and not scored | COBOL Identifier Dictionary |

See `docs/architecture.md` § Scope decisions for the rationale, and `docs/datasets.md` for per-dataset acquisition notes.

## Repository layout

```
parivartana/
  app/                Streamlit UI (Home + 7 pages)
  configs/            YAML for pipeline, datasets, models, evaluation
  src/
    pipeline/         Stage 1, 2, 3 implementations
    data/             Registry, loaders, ingestion, preprocessing
    evaluation/       CodeBLEU, execution accuracy, LLM judge
    grammars/         (reserved — empty; no full COBOL-85 grammar is shipped)
    utils/            Logging, paths, IO helpers
  data/               Local dataset storage (gitignored)
  artifacts/          Trained models, checkpoints, generated outputs
  scripts/            ingest.py, preprocess.py, run_app.sh
  tests/              Unit + integration
  docs/               architecture.md, datasets.md, ux_design.md
```

## Contributing

Contributions are welcome. Please read `CONTRIBUTING.md` for the development
setup, test commands, and pull-request conventions before opening a PR.

## License

Released under the MIT License. See `LICENSE` for the full text.
