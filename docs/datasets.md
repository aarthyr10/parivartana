# Datasets

The pipeline integrates nine public datasets registered in `configs/datasets.yaml`. Each dataset has a dedicated loader under `src/data/loaders/` and a slot under `data/raw/<key>/`.

## Registry

| Key | Name | Role | Samples |
| --- | --- | --- | --- |
| `nist_cobol` | NIST COBOL Test Suite | Gold evaluation | 2,400 |
| `ibm_open_cobol` | IBM Open COBOL Samples | Primary training | 800 |
| `codexglue` | CodeXGLUE Java to Python | Transfer pre-training | 110,000 |
| `stack_v2_cobol` | The Stack v2 COBOL subset | Encoder pre-training | 45,000 |
| `cosqa_codesearchnet` | CoSQA + CodeSearchNet | Docstring / identifier generation | 99,000 |
| `cobol_identifier_dict` | COBOL Identifier Dictionary | Renaming lookup | 12,500 |
| `fever_nli` | FEVER NLI Corpus | Semantic validation | 185,445 |
| `swe_bench` | SWE-bench Python subset | Execution evaluation | 2,294 |
| `gfg_multilingual` | GeeksForGeeks COBOL subset | OOD evaluation | 5,000 |

## Acquisition

Each dataset references its canonical source (HuggingFace dataset repo, GitHub repo, or NIST FTP) under `source.url` in `configs/datasets.yaml`. Place the downloaded corpus under the matching `local_path`. Run `python scripts/download_data.py --list` to print all keys and `python scripts/download_data.py --dataset <key>` to inspect the local status of a single dataset.

## Expected directory layout

```
data/raw/
  nist_cobol/                 .cob and .cbl source files, optional .expected stdout files alongside
  ibm_open_cobol/<domain>/    .cob files grouped by domain folder (banking, insurance, hr, ...)
  stack_v2_cobol/             flat .cob files
  gfg_multilingual/<algo>/    .cob files grouped by algorithm folder
  codexglue/                  *.jsonl with src_lang, tgt_lang, code, target, docstring
  cosqa_codesearchnet/        *.jsonl with intent, code, func_name, language, label
  cobol_identifier_dict/      *.jsonl with cobol_name, python_name, domain, confidence
  fever_nli/                  *.jsonl with id, claim, label, evidence
  swe_bench/                  *.jsonl with instance_id, repo, problem_statement, patch, test_patch
```

## Loader behaviour

All loaders honour the same contract: `iter_records()` yields dicts; `summarise(sample_size)` returns a `LoaderResult` with the first records and a count. `is_available()` returns `False` when the local path is empty so the UI and CLI can degrade gracefully without fabricating data.
