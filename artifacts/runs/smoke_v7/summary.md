# Batch run smoke_v7

- Dataset: **nist_cobol** (max=500)
- Judge providers: `['openai', 'anthropic']`
- Stage 3: **False**
- **Headline PASS rate: 99.8% (458/459)**

## Verdict distribution

| Verdict | Count | % |
|---|---:|---:|
| PASS | 53 | 11.5% |
| STRUCTURAL_PASS | 405 | 88.2% |
| FAIL | 1 | 0.2% |
| INCONCLUSIVE | 0 | 0.0% |

Stage 1 failures: 0

## Top failure patterns

### `failed_body_non_trivial`

- (1) 3/4 paragraphs have non-trivial bodies; stubbed: RL401M-START

