# Batch run neural50

- Dataset: **nist_cobol** (max=50)
- Judge providers: `['ollama']`
- Stage 3: **True**
- **Headline PASS rate: 0.0% (0/50)**
- **LLM-judge** (n=50): mean weighted **0.208**, mean correctness **0.078** (use this, not the 0.70 binary, where execution_match can't run)

## Verdict distribution

| Verdict | Count | % |
|---|---:|---:|
| PASS | 0 | 0.0% |
| STRUCTURAL_PASS | 0 | 0.0% |
| FAIL | 50 | 100.0% |
| INCONCLUSIVE | 0 | 0.0% |

Stage 1 failures: 0

## Top failure patterns

### `stage2_translator`

- (50) neural:Salesforce/codet5p-220m

### `failed_paragraph_coverage`

- (2) 0/1 paragraphs found as Python functions; missing: SORT-PARAGRAPH
- (2) 0/37 paragraphs found as Python functions; missing: OPEN-FILES, CCVS-INIT-FILE, 
- (2) 0/45 paragraphs found as Python functions; missing: DECLARATIVES, INPUT-ERROR-PR
- (2) 0/43 paragraphs found as Python functions; missing: OPEN-FILES, CCVS-INIT-FILE, 
- (1) 0/4 paragraphs found as Python functions; missing: DN4, CALL-TEST-1, CALL-TEST-2
- (1) 0/1 paragraphs found as Python functions; missing: IX302M-CONTROL
- (1) 0/3 paragraphs found as Python functions; missing: GRP-02, CALL-TEST-06, CALL-EX
- (1) 1/3 paragraphs found as Python functions; missing: SM301M-COPY, KSM31
- (1) 0/3 paragraphs found as Python functions; missing: DECLARATIVES, DECLARATIVES, D
- (1) 0/5 paragraphs found as Python functions; missing: CM303M-CONTROL, CM303M-DISABL

### `failed_identifier_coverage`

- (9) 0/88 identifiers traced into the Python; missing: PRINT-REC, DUMMY-RECORD, SQ-FS
- (3) 0/89 identifiers traced into the Python; missing: PRINT-REC, DUMMY-RECORD, SQ-FS
- (1) 0/9 identifiers traced into the Python; missing: DN1, DN2, DN3, DN4, DN5
- (1) 0/9 identifiers traced into the Python; missing: FREC, RKEY, SREC, SKEY, RREC
- (1) 0/15 identifiers traced into the Python; missing: PRINT-REC, DUMMY-RECORD, CONST
- (1) 0/2 identifiers traced into the Python; missing: FREC, RKEY
- (1) 0/2 identifiers traced into the Python; missing: CREC, CNAME1
- (1) 0/4 identifiers traced into the Python; missing: CREC, CNAME1, CQ, CINT
- (1) 0/16 identifiers traced into the Python; missing: PRINT-REC, DUMMY-RECORD, WS1, 
- (1) 0/9 identifiers traced into the Python; missing: SORT-LINK, PRINT-LINE-VALUES, P

### `failed_body_non_trivial`

- (3) 0/24 paragraphs have non-trivial bodies; stubbed: OPEN-FILES, CCVS-INIT-FILE, CL
- (2) 0/1 paragraphs have non-trivial bodies; stubbed: SORT-PARAGRAPH
- (2) 0/39 paragraphs have non-trivial bodies; stubbed: OPEN-FILES, CLOSE-FILES, INSPT
- (1) 0/1 paragraphs have non-trivial bodies; stubbed: CALL-TEST-2
- (1) 0/1 paragraphs have non-trivial bodies; stubbed: IX302M-CONTROL
- (1) 0/1 paragraphs have non-trivial bodies; stubbed: CALL-TEST-06
- (1) 0/1 paragraphs have non-trivial bodies; stubbed: DB301M-CONTROL
- (1) 0/1 paragraphs have non-trivial bodies; stubbed: CM303M-CONTROL
- (1) 0/1 paragraphs have non-trivial bodies; stubbed: CM401M-CONTROL
- (1) 0/1 paragraphs have non-trivial bodies; stubbed: PARA-IC109

### `failed_llm_judge`

- (13) [ollama] correctness=0.00, readability=0.20, pep8=0.30, pythonic=0.10, types=0.0
- (6) [ollama] correctness=0.00, readability=0.30, pep8=0.40, pythonic=0.20, types=0.1
- (5) [ollama] correctness=0.00, readability=0.00, pep8=0.00, pythonic=0.00, types=0.0
- (3) [ollama] correctness=0.00, readability=0.30, pep8=0.70, pythonic=0.20, types=1.0
- (2) [ollama] correctness=0.00, readability=0.30, pep8=0.20, pythonic=0.10, types=0.0
- (2) [ollama] correctness=0.00, readability=0.30, pep8=0.20, pythonic=0.10, types=0.4
- (2) [ollama] correctness=0.00, readability=0.30, pep8=0.40, pythonic=0.20, types=1.0
- (2) [ollama] correctness=0.10, readability=0.20, pep8=0.30, pythonic=0.40, types=0.5
- (2) [ollama] correctness=0.00, readability=0.10, pep8=0.20, pythonic=0.30, types=0.4
- (1) [ollama] correctness=0.20, readability=0.30, pep8=0.40, pythonic=0.10, types=0.5

### `failed_python_syntax_valid`

- (4) SyntaxError at line 26: unterminated string literal (detected at line 26)

### `failed_python_smoke`

- (3) exit=1, stderr_head=  File "/var/folders/rl/r9ygvg0x7_l7sdtfq9pq99fm0000gn/T/smo
- (3) exit=1, stderr_head=Traceback (most recent call last):

### `failed_execution_match`

- (5) stdout mismatch (stdout_mismatch)

