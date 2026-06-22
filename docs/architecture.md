# Architecture

## Pipeline

```
COBOL source
    |
    v
[Stage 1] FixedFormatPreprocessor -> CobolLexer -> CobolParser -> AST
    |
    v
[Stage 1] ComplexityScorer -> tier {simple, medium, high}
    |
    v
[Stage 2] NeuralTranslator (CodeT5+ on AST-linearised input)
    |       fallback: RuleBasedTranslator (deterministic templater)
    |
    v
[Stage 3] LLMRefiner -> IdentifierRenamer -> DocstringSynthesiser -> SemanticValidator
    |
    v
Refined Python
```

## Module map

| Layer | Path | Purpose |
| --- | --- | --- |
| App | `app/` | Streamlit entry point and pages |
| Pipeline | `src/pipeline/stage1_parser/` | Fixed-format handling, lexing, parsing, complexity |
| Pipeline | `src/pipeline/stage2_neural/` | CodeT5+ wrapper, rule-based baseline, curriculum scheduler, trainer |
| Pipeline | `src/pipeline/stage3_llm/` | Provider adapters, renamer, refiner, docstring synth, NLI validator |
| Data | `src/data/` | Registry with priority tags, loaders, preprocessing, ingestion adapters |
| Evaluation | `src/evaluation/` | CodeBLEU, execution accuracy, LLM judge |
| Utils | `src/utils/` | Config, paths, logging, IO |
| Configs | `configs/` | YAML for pipeline, datasets, models, evaluation |

## Configuration loading

`src/utils/config.load_config(name)` reads `configs/<name>.yaml`. The pipeline config is parsed through a Pydantic schema; the others are returned as raw dictionaries. Configuration is cached with `lru_cache` and can be cleared with `reload_config`.

## Data flow during preprocessing

`CobolPreprocessor` accepts dataset records (dicts with `id` and `source` fields) and returns one `ProcessedRow` per record. Each row carries the assigned tier, raw complexity score, and per-feature breakdown so downstream tier-stratified sampling and curriculum scheduling can work directly on the produced JSONL.

## Stage 2 contract

`NeuralTranslator.translate(ast, tier)` takes a parsed AST and the assigned tier and returns a `TranslationResult`. The encode-generate-decode block runs against a HuggingFace seq2seq backbone (default `Salesforce/codet5p-220m`) with tier-aware beam search and structural special tokens (`[DIV] [SEC] [PARA] [STMT] [EXPR]`). If transformers/torch or the checkpoint is unreachable, the call transparently falls back to the deterministic `RuleBasedTranslator` and records `metadata["fallback"] = True`.

`CurriculumTrainer` orchestrates fine-tuning with a tier-release schedule driven by validation CodeBLEU plateaus. The scheduler can be exercised in dry-run mode without `torch` so the curriculum logic is unit-testable.

## Stage 3 contract

`LLMRefiner.refine(raw_python, tier, cobol_identifiers, cobol_comment, ...)` is provider-agnostic. The orchestrator runs five steps and degrades each independently: dictionary-first rename, tier-aware LLM rewrite, docstring synthesis, HIGH-tier review banner, semantic validation. Provider classes implement `is_available` and `complete(system, user)`; when the configured provider has no API key, the refiner records `llm_refine:no_provider` in `metadata["pipeline_steps"]` and returns the renamed source. The `SemanticValidator` falls back to a token-Jaccard heuristic when the DeBERTa NLI model cannot be loaded.

## Evaluation contract

`CodeBleuScorer.score(reference, hypothesis)` returns the four CodeBLEU components and the weighted final score. `ExecutionAccuracy.compare(cobol, python)` compiles the COBOL with GnuCOBOL, runs both binaries, and returns matched stdout plus error type. `LlmJudge.score(cobol, python)` returns a five-dimension rubric with the configured weights.

---

## Scope decisions (recorded after the P3 proposal review, May 2026)

The reviewing professor's feedback flagged scope risk on two axes: dataset count and parser ambition. Both points are valid in the abstract, and both warranted explicit decisions rather than silent expansion. The two decisions below are the new ground truth for the project.

### Stage 1 is a thin preprocessor, not a COBOL-85 grammar

The Stage 1 implementation is intentionally a ~250-line hand-written lexer + recursive-descent parser, not an ANTLR4 grammar. It strips fixed-format column metadata, recognises divisions/paragraphs/data items/a verb vocabulary of ~25 statements, and produces an AST shallow enough to feed the complexity scorer. There is no `Cobol85.g4` in `src/grammars/` and `antlr4-python3-runtime` is not imported anywhere — the dependency listed in `pyproject.toml` is unused and kept only for forward compatibility.

Justification for keeping Stage 1 rather than feeding raw COBOL into CodeT5+:

* The Simple/Medium/High **tier signal** drives the curriculum scheduler. Without it, the "Curriculum CodeT5+" method (one of the four claimed novelties) loses its release schedule and reduces to ordinary fine-tuning.
* Tier classification also drives the **HIGH-tier review banner** in Stage 3, which is what makes the system safe to put in front of a human reviewer for the 10% of programs the proposal acknowledges cannot be fully auto-converted.
* The parser feeds **structural special tokens** (`[DIV] [SEC] [PARA] [STMT] [EXPR]`) into the Stage 2 encoder. These give the model an unambiguous serialisation that does not depend on whitespace or comment fidelity in the raw COBOL.

We are **not** investing more engineering in Stage 1. No COBOL-85 grammar work, no copybook resolution, no EXEC SQL parsing. The shipped parser handles the sample programs and the IBM samples; constructs it cannot handle land in the HIGH tier and are surfaced for human review.

### Active dataset set is four, not nine

Of the nine datasets enumerated in the P3 proposal, four are designated `priority: P0` (active, pulled by `--all`):

| Key | Role | Why P0 |
| --- | --- | --- |
| `nist_cobol` | Gold evaluation | Verified outputs are required for execution accuracy |
| `ibm_open_cobol` | Primary training | The COBOL→Python parallel signal during fine-tuning |
| `codexglue` | Transfer pretraining | Java→Python similarity is the outer loop of the 2-D curriculum |
| `fever_nli` | Semantic validation | Trains the NLI validator — the singled-out novel contribution |

`cobol_identifier_dict` is also P0 but ships with the repository, so it has no ingestion cost.

The remaining four datasets — `stack_v2_cobol`, `cosqa_codesearchnet`, `swe_bench`, `gfg_multilingual` — are tagged `priority: P2` (deferred). Their ingestion adapters remain in the codebase so they can be re-enabled cheaply, but `scripts/ingest.py --all` skips them by default. Use `--include-deferred` or `--priority P2` to opt back in.

Justification: the headline claims (curriculum gain over Java-only transfer, NLI catches semantic drift, dictionary-renamed Python is more readable than COB2PY) all rest on the P0 set. Pulling 285,000 records when 12,500 + the IBM/NIST programs answer the research question is poor return on time invested.
