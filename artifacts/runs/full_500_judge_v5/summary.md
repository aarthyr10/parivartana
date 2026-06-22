# Batch run full_500_judge_v5

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

### `stage1_cobc_status`

- (317) rejected
- (183) accepted

### `our_parser_accepted_cobc_rejected`

- (1) K1SEA
- (1) K1WKY
- (1) ALTL1
- (1) K3OCA
- (1) K1WKZ
- (1) KK208A
- (1) KSM31
- (1) ALTLB
- (1) K3IOA
- (1) K2PRA

### `stage3_skipped`

- (112) tier=simple below medium

### `failed_execution_match`

- (500) stdout mismatch (cobol_compiler_not_found)

### `failed_body_non_trivial`

- (2) 25/31 paragraphs have non-trivial bodies; stubbed: TEST-2, TEST-2-2, TEST-2-3, T
- (2) 45/51 paragraphs have non-trivial bodies; stubbed: SEQ-TEST-WR-01-LOOP, SEQ-TEST
- (2) 28/33 paragraphs have non-trivial bodies; stubbed: REL-TEST-003-R, REL-TEST-004-
- (1) 3/4 paragraphs have non-trivial bodies; stubbed: RL401M-START
- (1) 8/9 paragraphs have non-trivial bodies; stubbed: RECEIVE-ECHO-AND-LOG
- (1) 8/10 paragraphs have non-trivial bodies; stubbed: CM104M-POLL-1, CM104M-POLL-2
- (1) 3/7 paragraphs have non-trivial bodies; stubbed: NC401M-ARITHEXP, NC401M-SIGCOND
- (1) 46/52 paragraphs have non-trivial bodies; stubbed: WRITE-TEST-001-01, WRITE-TEST
- (1) 39/47 paragraphs have non-trivial bodies; stubbed: SEQ-TEST-001, SEQ-TEST-002, S
- (1) 32/36 paragraphs have non-trivial bodies; stubbed: REL-TEST-001, REL-INIT-1, REL

