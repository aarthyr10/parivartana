# Batch run full_500_judge_v8

- Dataset: **nist_cobol** (max=500)
- Judge providers: `['openai', 'anthropic']`
- Stage 3: **True**
- **Headline PASS rate: 80.8% (371/459)**

## Verdict distribution

| Verdict | Count | % |
|---|---:|---:|
| PASS | 49 | 10.7% |
| STRUCTURAL_PASS | 322 | 70.2% |
| FAIL | 88 | 19.2% |
| INCONCLUSIVE | 0 | 0.0% |

Stage 1 failures: 0

## Top failure patterns

### `stage1_cobc_status`

- (269) rejected
- (190) accepted

### `our_parser_accepted_cobc_rejected`

- (1) SM106A
- (1) IX302M
- (1) RL302M
- (1) SQ302M
- (1) SM301M
- (1) IF402M
- (1) SM401M
- (1) CM401M
- (1) SQ401M
- (1) ST120A

### `stage3_skipped`

- (62) tier=simple below medium

### `failed_execution_match`

- (4) stdout mismatch (stdout_mismatch)

### `failed_body_non_trivial`

- (2) 25/31 paragraphs have non-trivial bodies; stubbed: TEST-2, TEST-2-2, TEST-2-3, T
- (2) 45/51 paragraphs have non-trivial bodies; stubbed: SEQ-TEST-WR-01-LOOP, SEQ-TEST
- (2) 28/33 paragraphs have non-trivial bodies; stubbed: REL-TEST-003-R, REL-TEST-004-
- (1) 8/9 paragraphs have non-trivial bodies; stubbed: RECEIVE-ECHO-AND-LOG
- (1) 8/10 paragraphs have non-trivial bodies; stubbed: CM104M-POLL-1, CM104M-POLL-2
- (1) 3/7 paragraphs have non-trivial bodies; stubbed: NC401M-ARITHEXP, NC401M-SIGCOND
- (1) 46/52 paragraphs have non-trivial bodies; stubbed: WRITE-TEST-001-01, WRITE-TEST
- (1) 39/47 paragraphs have non-trivial bodies; stubbed: SEQ-TEST-001, SEQ-TEST-002, S
- (1) 32/36 paragraphs have non-trivial bodies; stubbed: REL-TEST-001, REL-INIT-1, REL
- (1) 37/44 paragraphs have non-trivial bodies; stubbed: INDEX-TEST-1, INDEX-TEST-2, I

