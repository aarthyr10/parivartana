# Batch run full_500_judge

- Dataset: **nist_cobol** (max=500)
- Judge providers: `['openai', 'anthropic']`
- Stage 3: **True**

## Verdict distribution

| Verdict | Count | % |
|---|---:|---:|
| PASS | 0 | 0.0% |
| FAIL | 25 | 5.0% |
| INCONCLUSIVE | 475 | 95.0% |

Stage 1 failures: 0

## Top failure patterns

### `stage3_error`

- (500) AttributeError

### `judge_skipped_reason`

- (473) anthropic: judge call failed (Error code: 401 - {'type': 'error', 'error': {'typ
- (2) anthropic: judge call failed (<html>
<head><title>502 Bad Gateway</title></head

### `failed_paragraph_coverage`

- (2) 16/28 paragraphs found as Python functions; missing: WRT-LN, BLANK-LINE-PRINT, F
- (2) 20/34 paragraphs found as Python functions; missing: FAIL-ROUTINE-EX, BAIL-OUT, 
- (1) 3/5 paragraphs found as Python functions; missing: CNAME1, CNAME1
- (1) 23/29 paragraphs found as Python functions; missing: BAIL-OUT-EX, CCVS1-EXIT, ST
- (1) 19/29 paragraphs found as Python functions; missing: FAIL-ROUTINE-WRITE, FAIL-RO
- (1) 26/30 paragraphs found as Python functions; missing: WRITE-TEST-GF-01, SQ210M-EN
- (1) 22/30 paragraphs found as Python functions; missing: BAIL-OUT-WRITE, BAIL-OUT-EX
- (1) 23/32 paragraphs found as Python functions; missing: BAIL-OUT-EX, CCVS1-EXIT, ST
- (1) 23/27 paragraphs found as Python functions; missing: END-RTN-EXIT, CCVS1-EXIT, L
- (1) 21/41 paragraphs found as Python functions; missing: FAIL-ROUTINE-WRITE, FAIL-RO

### `failed_identifier_coverage`

- (1) 0/4 identifiers traced into the Python; missing: FREC, RKEY, FREC2, RKEY2
- (1) 0/5 identifiers traced into the Python; missing: FREC, RKEY, VARIABLES, VKEY, RR
- (1) 39/72 identifiers traced into the Python; missing: TEST-RESULTS, PAR-NAME, TEST-

### `failed_python_syntax_valid`

- (1) SyntaxError at line 248: expected an indented block after function definition on
- (1) SyntaxError at line 239: unterminated string literal (detected at line 239)
- (1) SyntaxError at line 249: invalid syntax
- (1) SyntaxError at line 257: unterminated string literal (detected at line 257)
- (1) SyntaxError at line 249: expected ':'
- (1) SyntaxError at line 250: unterminated string literal (detected at line 250)

