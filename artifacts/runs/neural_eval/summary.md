# Batch run neural_eval

- Dataset: **nist_cobol** (max=2000)
- Judge providers: `['openai', 'anthropic']`
- Stage 3: **True**
- **Headline PASS rate: 0.0% (0/459)**
- **LLM-judge** (n=459): mean weighted **0.542**, mean correctness **0.166** (use this, not the 0.70 binary, where execution_match can't run)

## Verdict distribution

| Verdict | Count | % |
|---|---:|---:|
| PASS | 0 | 0.0% |
| STRUCTURAL_PASS | 0 | 0.0% |
| FAIL | 459 | 100.0% |
| INCONCLUSIVE | 0 | 0.0% |

Stage 1 failures: 0

## Top failure patterns

### `stage2_translator`

- (459) neural:Salesforce/codet5p-220m

### `failed_llm_judge`

- (40) [openai] correctness=0.00, readability=0.50, pep8=1.00, pythonic=0.20, types=1.0
- (30) [openai] correctness=0.00, readability=0.80, pep8=1.00, pythonic=0.60, types=1.0
- (28) [openai] correctness=0.00, readability=0.60, pep8=1.00, pythonic=0.40, types=1.0
- (22) [openai] correctness=0.00, readability=0.60, pep8=1.00, pythonic=0.50, types=1.0
- (18) [openai] correctness=0.20, readability=0.80, pep8=1.00, pythonic=0.60, types=1.0
- (18) [openai] correctness=0.00, readability=0.70, pep8=1.00, pythonic=0.50, types=1.0
- (16) [openai] correctness=0.00, readability=0.60, pep8=0.80, pythonic=0.40, types=1.0
- (13) [openai] correctness=0.20, readability=0.60, pep8=0.80, pythonic=0.50, types=1.0
- (11) [openai] correctness=0.20, readability=0.70, pep8=1.00, pythonic=0.50, types=1.0
- (11) [openai] correctness=0.40, readability=0.70, pep8=0.90, pythonic=0.60, types=1.0

### `failed_paragraph_coverage`

- (7) 0/64 paragraphs found as Python functions; missing: OPEN-FILES, CLOSE-FILES, TER
- (7) 0/57 paragraphs found as Python functions; missing: OPEN-FILES, CLOSE-FILES, TER
- (7) 0/87 paragraphs found as Python functions; missing: OPEN-FILES, CCVS-INIT-FILE, 
- (6) 0/70 paragraphs found as Python functions; missing: OPEN-FILES, CCVS-INIT-FILE, 
- (6) 0/69 paragraphs found as Python functions; missing: DECLARATIVES, INPUT-PROCESS,
- (5) 0/3 paragraphs found as Python functions; missing: DECLARATIVES, DECLARATIVES, D
- (5) 0/39 paragraphs found as Python functions; missing: OPEN-FILES, CCVS-INIT-FILE, 
- (5) 0/36 paragraphs found as Python functions; missing: OPEN-FILES, CCVS-INIT-FILE, 
- (5) 0/46 paragraphs found as Python functions; missing: OPEN-FILES, CLOSE-FILES, TER
- (4) 0/40 paragraphs found as Python functions; missing: OPEN-FILES, CCVS-INIT-FILE, 

### `failed_identifier_coverage`

- (22) 0/88 identifiers traced into the Python; missing: PRINT-REC, DUMMY-RECORD, SQ-FS
- (10) 0/106 identifiers traced into the Python; missing: PRINT-REC, DUMMY-RECORD, IX-F
- (9) 0/89 identifiers traced into the Python; missing: PRINT-REC, DUMMY-RECORD, SQ-FS
- (7) 0/106 identifiers traced into the Python; missing: PRINT-REC, DUMMY-RECORD, RL-F
- (6) 0/84 identifiers traced into the Python; missing: PRINT-REC, DUMMY-RECORD, SQ-FS
- (5) 0/166 identifiers traced into the Python; missing: PRINT-REC, DUMMY-RECORD, WRK-
- (4) 0/2 identifiers traced into the Python; missing: FREC, RKEY
- (4) 0/100 identifiers traced into the Python; missing: PRINT-REC, DUMMY-RECORD, IX-F
- (3) 0/5 identifiers traced into the Python; missing: TEST-AREA, TEST1, TEST2, TEST3,
- (3) 0/86 identifiers traced into the Python; missing: PRINT-REC, DUMMY-RECORD, RL-FS

### `failed_body_non_trivial`

- (8) 0/51 paragraphs have non-trivial bodies; stubbed: OPEN-FILES, CCVS-INIT-FILE, CL
- (7) 0/28 paragraphs have non-trivial bodies; stubbed: OPEN-FILES, CLOSE-FILES, INSPT
- (7) 0/24 paragraphs have non-trivial bodies; stubbed: OPEN-FILES, CCVS-INIT-FILE, CL
- (7) 0/45 paragraphs have non-trivial bodies; stubbed: OPEN-FILES, CLOSE-FILES, INSPT
- (6) 0/48 paragraphs have non-trivial bodies; stubbed: INPUT-PROCESS, D-C-TEST-GF-01-
- (5) 0/22 paragraphs have non-trivial bodies; stubbed: OPEN-FILES, CLOSE-FILES, INSPT
- (5) 0/39 paragraphs have non-trivial bodies; stubbed: OPEN-FILES, CLOSE-FILES, INSPT
- (5) 0/66 paragraphs have non-trivial bodies; stubbed: OPEN-FILES, CCVS-INIT-FILE, CL
- (4) 0/33 paragraphs have non-trivial bodies; stubbed: OPEN-FILES, CCVS-INIT-FILE, CL
- (4) 0/32 paragraphs have non-trivial bodies; stubbed: OPEN-FILES, CCVS-INIT-FILE, CL

### `failed_python_smoke`

- (20) exit=1, stderr_head=Traceback (most recent call last):

### `failed_execution_match`

- (109) stdout mismatch (stdout_mismatch)

### `stage3_llm_truncated`

- (4) max_tokens hit

