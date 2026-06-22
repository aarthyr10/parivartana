# PARIVARTANA — final results report

Auto-generated from `artifacts/runs/rule50` and `artifacts/runs/neural50`. Gate = 0.7.

## Head-to-head (same programs, same oracle)

| System | Files | Judge mean | PASS@gate | Exec-match | CodeBLEU |
|---|---|---|---|---|---|
| Rule baseline (Stage 2) | 51 | 0.523 | 32.0% | 3/7 (42.9%) | None |
| Neural CodeT5+ (curriculum + LoRA) | 51 | 0.208 | 0.0% | 2/7 (28.6%) | None |

**Best by judge correctness: rule** (neural − rule = -0.315).

## Against the proposal metrics

- **LLM-as-judge**: reported above (the only correctness oracle that runs on
  the full NIST CCVS corpus).
- **Execution accuracy**: reported above on the self-contained subset that
  runs standalone under GnuCOBOL.
- **CodeBLEU**: not enabled in these runs.
- **pass@1 (SWE-bench)**: deferred (P2 dataset).
- **Human study (200 progs)**: not done.

## Figures (academic)

- `docs/figures/model_module_tree.svg` — CodeT5+ layer/module tree.
- `docs/figures/forward_graph.svg` — forward computation graph.
- `docs/figures/curriculum_tree.svg` — two-dimensional curriculum.
- `docs/figures/ast_neural_pipeline.svg` — AST → CodeT5+ → Python.

## Verdict breakdown

- rule: {'PASS': 16, 'FAIL': 34}
- neural: {'FAIL': 50}

## Honest conclusion

The full three-stage pipeline runs end-to-end and the curriculum-trained
CodeT5+ model is a real, evaluated artifact. The rule-based draft remains the
strongest single stage by the judge; the neural model's gap is driven by
training-data volume/quality (few execution-verified gold pairs, mostly
unverified silver, no Python warm-start). The next levers are: a Python
warm-start phase, more gold via forward-synthesis/COBOLEval, and
gold-weighted / fewer-epoch training to avoid overfitting silver.