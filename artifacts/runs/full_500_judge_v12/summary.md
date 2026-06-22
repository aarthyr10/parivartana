# Batch run full_500_judge_v12

- Dataset: **nist_cobol** (max=500)
- Judge providers: `[]`
- Stage 3: **False**
- **Headline PASS rate: 68.4% (314/459)**

## Verdict distribution

| Verdict | Count | % |
|---|---:|---:|
| PASS | 145 | 31.6% |
| STRUCTURAL_PASS | 169 | 36.8% |
| FAIL | 145 | 31.6% |
| INCONCLUSIVE | 0 | 0.0% |

Stage 1 failures: 0

## Top failure patterns

### `failed_execution_match`

- (128) stdout mismatch (stdout_mismatch)

### `failed_python_smoke`

- (11) exit=0, stderr_head=runtime: TypeError: unsupported operand type(s) for +: 'None
- (5) exit=0, stderr_head=runtime: NameError: name 'ccvs1' is not defined
- (1) exit=0, stderr_head=runtime: FileNotFoundError: [Errno 2] No such file or direct
- (1) exit=0, stderr_head=runtime: NameError: name 'head_routine' is not defined

