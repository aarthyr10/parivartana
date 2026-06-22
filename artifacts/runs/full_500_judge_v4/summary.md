# Batch run full_500_judge_v4

- Dataset: **nist_cobol** (max=500)
- Judge providers: `['openai', 'anthropic']`
- Stage 3: **True**

## Verdict distribution

| Verdict | Count | % |
|---|---:|---:|
| PASS | 0 | 0.0% |
| FAIL | 500 | 100.0% |
| INCONCLUSIVE | 0 | 0.0% |

Stage 1 failures: 0

## Top failure patterns

### `stage3_skipped`

- (112) tier=simple below medium

### `failed_execution_match`

- (500) stdout mismatch (cobol_compiler_not_found)

