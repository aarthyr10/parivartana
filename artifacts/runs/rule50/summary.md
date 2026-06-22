# Batch run rule50

- Dataset: **nist_cobol** (max=50)
- Judge providers: `['ollama']`
- Stage 3: **True**
- **Headline PASS rate: 32.0% (16/50)**
- **LLM-judge** (n=50): mean weighted **0.523**, mean correctness **0.578** (use this, not the 0.70 binary, where execution_match can't run)

## Verdict distribution

| Verdict | Count | % |
|---|---:|---:|
| PASS | 16 | 32.0% |
| STRUCTURAL_PASS | 0 | 0.0% |
| FAIL | 34 | 68.0% |
| INCONCLUSIVE | 0 | 0.0% |

Stage 1 failures: 0

## Top failure patterns

### `stage2_translator`

- (50) rule-based

### `failed_llm_judge`

- (7) [ollama] correctness=0.50, readability=0.30, pep8=0.20, pythonic=0.10, types=0.9
- (6) [ollama] correctness=0.20, readability=0.30, pep8=0.40, pythonic=0.10, types=0.5
- (4) [ollama] correctness=0.50, readability=0.30, pep8=0.40, pythonic=0.20, types=0.7
- (4) [ollama] correctness=0.20, readability=0.30, pep8=0.40, pythonic=0.10, types=0.9
- (2) [ollama] correctness=0.80, readability=0.50, pep8=0.70, pythonic=0.40, types=1.0
- (1) [ollama] correctness=0.50, readability=0.30, pep8=0.40, pythonic=0.20, types=0.9
- (1) [ollama] correctness=0.80, readability=0.50, pep8=0.70, pythonic=0.40, types=0.9
- (1) [ollama] correctness=0.80, readability=0.60, pep8=0.50, pythonic=0.40, types=0.9
- (1) [ollama] correctness=0.80, readability=0.60, pep8=0.50, pythonic=0.40, types=0.7
- (1) [ollama] correctness=0.20, readability=0.30, pep8=0.10, pythonic=0.10, types=0.9

### `failed_execution_match`

- (4) stdout mismatch (stdout_mismatch)

### `failed_python_smoke`

- (4) exit=0, stderr_head=runtime: TypeError: unsupported operand type(s) for +=: 'Non

### `failed_body_non_trivial`

- (1) 39/47 paragraphs have non-trivial bodies; stubbed: SEQ-TEST-001, SEQ-TEST-002, S
- (1) 32/36 paragraphs have non-trivial bodies; stubbed: REL-TEST-001, REL-INIT-1, REL

