# Conversion-quality audit — issues, libraries, regex wins, plan

## The deeper truth the verifier was hiding

The `full_500_judge_v3` run showed 0 PASS, 0 FAIL, 500 INCONCLUSIVE — and
the obvious story was "OpenAI is out of credits, that's the only thing
left." That's true at the verdict level. But scanning the actual
refined Python tells a different, more uncomfortable story:

| Metric                              |          Value | What it means                                           |
|-------------------------------------|---------------:|---------------------------------------------------------|
| Functions emitted (total, 500 progs)|         38,951 |                                                         |
| Functions with `pass`-only bodies   |     **4,110**  | **10.5 %** of all "translated" functions are empty stubs |
| Stage-2 warnings of "body replaced with pass+TODO" | hundreds | The rule-based engine gave up on this paragraph |
| Stage-2 warnings of "repaired N unparseable line(s)" | hundreds | Statements silently dropped or commented out      |
| Stage-2 warnings "orphan ELSE skipped" |         42 | IF/ELSE blocks getting dropped at parse time           |
| `IF402M` worst case                 | 15/17 funcs stubbed | Whole NIST programs are essentially `def x(): pass × N` |

The verifier scores those as PASS-ready because it only asks "does
`def x():` exist and are the identifier names referenced somewhere?"
— not "does the function body actually do anything." `IF402M` (a NIST
test of `FUNCTION LENGTH`, `FUNCTION LOG`, `FUNCTION MEAN`, etc.) ships
with **every paragraph empty** and the verifier reports 100 %
paragraph_coverage and 100 % identifier_coverage.

So the headline isn't "we need an LLM judge to finish the run." It's
"the rule-based Stage 2 stubs a meaningful fraction of every
real-world COBOL program, and the verifier doesn't notice."

## Top constructs the rule-based engine silently stubs

Counted across the 500-program NIST corpus:

| Construct          | Files | What it does in COBOL                                |
|--------------------|------:|------------------------------------------------------|
| `INSPECT`          |   772 | String count / replace / tally                       |
| `COMP` / `COMP-3`  |   451 | Packed-decimal numeric storage                       |
| `REDEFINES`        |   388 | Memory aliasing of one variable over another         |
| `CALL`             |   312 | Invoke another COBOL program                         |
| `OCCURS`           |   278 | Fixed-size arrays (often with `INDEXED BY`)          |
| `AT END`           |   168 | End-of-file handler on `READ`                        |
| `INVALID KEY`      |   137 | I/O exception handler                                |
| `FUNCTION xxx`     |    92 | Intrinsic functions (`LENGTH`, `LOG`, `MAX`, `MEAN`) |

Every one of these is in the rule-based engine's blind spot today.
The verb table in `src/pipeline/stage2_neural/rule_based.py` covers 45
verbs, but COBOL expressivity is in the **clauses and modifiers**, not
just the verbs. `READ FILE-X AT END PERFORM EOF-RTN` only emits real
Python if the parser carries the `AT END` clause through; ours
doesn't.

## What's actually available in the Python ecosystem (mid-2026)

After a real survey:

### Pre-parse / sanity gate
- **GnuCOBOL `cobc -fsyntax-only file.cbl`** — fastest, most accurate
  syntax check available. GPL-3. `brew install gnucobol` on Mac,
  `apt-get install gnucobol` on Debian/Ubuntu. Already in your
  pipeline auto-detect. (No usable IR dump for re-targeting; just
  syntax check.)

### Python-native COBOL parsers
- **`cobol-parser`** (a.k.a. legacylens-cobol-parser on PyPI but
  imports as `cobol_parser`, MIT, last release April 2025) — **NOT a
  full-AST parser.** Extracts only CALLs, file I/O, PERFORMs, SQL
  queries, copybook inclusions via regex. Useful as a *second opinion*
  for our CALL/PERFORM lists; useless for the verb translation work.
  Confirmed working on `IF402M` from the corpus.
- **`pycobol`** (PyPI, last release 2023) — DATA-DIVISION only,
  abandoned-ish. Skip.
- **`coboljsonifier` / `cobolio`** — copybook + EBCDIC data file
  decoding. Useful only if we need to **run** the translated Python
  against real mainframe data files.
- **antlr4 + grammars-v4/cobol85** — generates a real ANTLR Python
  parser from `Cobol85.g4`. **No pre-built wheel exists**; we'd run
  `antlr4 -Dlanguage=Python3 Cobol85.g4` ourselves. This is the only
  path to a full Python-native COBOL85 AST without a JVM.
- **ProLeap (Java, MIT, v2.4.0 April 2024)** — gold-standard parser,
  passes the NIST suite. No PyPI wrapper. Reachable via `jpype1`
  calling the published JAR, or shell out to a thin Java CLI we
  control.

### PIC / COMP-3 / EBCDIC
- **Stingray Reader** — pure Python, full PIC / COMP-3 / EBCDIC
  decoding. Lets us actually model `PIC S9(4)V99 COMP-3` as a
  `decimal.Decimal` with the right scale instead of `0`.
- **COBOL DDE** — narrower scope, same idea. Stingray is the better bet.

### End-to-end COBOL→Python converters
- **None production-grade.** The GitHub repos that claim to do this
  (`Cobol2PY`, `cobol-converter`, `CodeMigrate`) are LLM-agent demos,
  not maintained libraries. We are not behind the open-source
  state-of-the-art — there isn't one.

## Regex wins (concrete patterns the rule engine should catch but doesn't)

Each of these is a self-contained transform — minutes of work, fixes
hundreds of paragraphs. Listed in descending leverage:

### R1. Strip fixed-format margins before parsing
```python
SEQ_NUM    = re.compile(r"^[0-9 ]{6}")        # cols 1-6
RIGHT_TAG  = re.compile(r".{72}\K.*")          # cols 73-80 garbage
COMMENT_C7 = re.compile(r"^[ 0-9]{6}\*")       # column 7 == '*'  → comment
CONT_C7    = re.compile(r"^[ 0-9]{6}-")        # column 7 == '-'  → continuation
```
NIST programs are full of `IF4024.2` right-margin tags that the
current parser may or may not strip cleanly. The 38 distinct
`repaired N unparseable line(s)` warnings strongly suggest this isn't
fully working.

### R2. Decode intrinsic functions
```python
INTRINSIC = {
    "LENGTH":     lambda args: f"len({args[0]})",
    "LOG":        lambda args: f"math.log({args[0]})",
    "LOG10":      lambda args: f"math.log10({args[0]})",
    "MAX":        lambda args: f"max({', '.join(args)})",
    "MIN":        lambda args: f"min({', '.join(args)})",
    "MEAN":       lambda args: f"statistics.mean([{', '.join(args)}])",
    "MEDIAN":     lambda args: f"statistics.median([{', '.join(args)}])",
    "MOD":        lambda args: f"({args[0]} % {args[1]})",
    "NUMVAL":     lambda args: f"float({args[0]})",
    "LOWER-CASE": lambda args: f"{args[0]}.lower()",
    "UPPER-CASE": lambda args: f"{args[0]}.upper()",
    "ORD":        lambda args: f"ord({args[0]})",
    "ORD-MAX":    lambda args: f"max(range(len({args[0]})), key=lambda i: {args[0]}[i])+1",
    "ORD-MIN":    lambda args: f"min(range(len({args[0]})), key=lambda i: {args[0]}[i])+1",
}
PATTERN = re.compile(r"FUNCTION\s+([A-Z\-]+)\s*\(([^)]*)\)")
```
This single transform un-stubs `IF402M` (15/17 paragraphs) and the
other intrinsic-function tests.

### R3. PIC clause → Python type hint + initializer
```python
# Examples:
# PIC X(10)            → str, default "" * 10
# PIC 9(5)             → int, default 0
# PIC 9(5)V99          → Decimal, scale=2
# PIC S9(4) COMP-3     → Decimal, scale=0, signed (packed)
# PIC S9(4)V99 COMP-3  → Decimal, scale=2, signed (packed)
PIC_RE = re.compile(r"PIC(?:TURE)?\s+IS?\s+(S?)9*(?:\((\d+)\))?(?:V9*(?:\((\d+)\))?)?(?:\s+(COMP-?3|COMP|PACKED-DECIMAL))?")
```
Today the data section emits `value = 0 if name.startswith(('ws_num',
'ws_count', …)) else ''` — a fragile heuristic on the variable name.
A real PIC parser fixes that for 451/500 programs.

### R4. AT END / INVALID KEY clauses
```python
AT_END     = re.compile(r"\bAT\s+END\b", re.IGNORECASE)
NOT_AT_END = re.compile(r"\bNOT\s+AT\s+END\b", re.IGNORECASE)
INVALID    = re.compile(r"\bINVALID\s+KEY\b", re.IGNORECASE)
```
Translate to a `try: … except EOFError:` block. 168 + 137 programs use
these and currently lose their error handlers entirely.

### R5. INSPECT TALLYING / REPLACING
```python
# INSPECT name TALLYING counter FOR ALL "X"     → counter += name.count("X")
# INSPECT name REPLACING ALL "X" BY "Y"         → name = name.replace("X", "Y")
INSPECT_TALLY   = re.compile(r"INSPECT\s+(\w[\w-]*)\s+TALLYING\s+(\w[\w-]*)\s+FOR\s+ALL\s+\"([^\"]+)\"")
INSPECT_REPLACE = re.compile(r"INSPECT\s+(\w[\w-]*)\s+REPLACING\s+ALL\s+\"([^\"]+)\"\s+BY\s+\"([^\"]+)\"")
```
772 occurrences across the corpus.

### R6. OCCURS / INDEXED BY
```python
# 05 WS-TABLE OCCURS 10 TIMES INDEXED BY WS-IDX  →  ws_table: list = [None] * 10
OCCURS_RE = re.compile(r"OCCURS\s+(\d+)\s+TIMES(?:\s+INDEXED\s+BY\s+(\w[\w-]*))?")
```
278/500 programs use OCCURS. Today these collapse to a single scalar.

## Concrete recommendation, ordered by leverage

A 4-step "Stage 1.5" interlude between parsing and code-gen, plus one
verifier hardening:

### Step A. Pre-flight gate with `cobc -fsyntax-only`
Add `src/pipeline/stage1_parser/cobc_preflight.py` that shells out to
`cobc -fsyntax-only -free` for each program. If GnuCOBOL rejects the
file, the trace records `stage1_cobc_status="rejected"` with the cobc
stderr — separating "your COBOL is broken" from "our parser doesn't
understand your COBOL." Free, deterministic, no API needed. Cost:
~50 LOC, runs in <50 ms per program.

### Step B. Regex normalisation pre-pass (R1-R6)
A new `src/pipeline/stage1_parser/normaliser.py` runs the six regex
transforms above on the COBOL source *before* tokenisation. This
turns `FUNCTION LENGTH("ABC")` into a normalised
`__LENGTH("ABC")` token that the existing lexer can route to a verb
handler we add. Same for `INSPECT TALLYING`, `OCCURS`, `AT END`. Cost:
~300 LOC of regex + matching new verb handlers. Unstubs an estimated
1,500–2,500 of the 4,110 currently-empty function bodies.

### Step C. Stingray-backed PIC clause decoder
Replace the heuristic `_default_for_pic` in `rule_based.py` with a
`stingray`-driven `pic_decoder.py` that returns the right Python type
+ default + scale + sign. `pip install stingray-reader`. Fixes 451/500
programs whose data section currently has type-soup variables. Cost:
~150 LOC + 1 dep.

### Step D. `cobol_parser` (legacylens) as second-opinion CALL/PERFORM extractor
A tiny module that re-parses each program with `cobol_parser` and
**diffs the CALL/PERFORM lists against our AST**. Any CALL that
appears in legacylens but not in our AST is an under-coverage signal
that goes into `patterns.json`. Cost: ~80 LOC + 1 dep. Doesn't change
codegen; gives us a *quality metric* we currently lack.

### Step E. Verifier "body non-trivial" check
This is the missing structural check. Right now `paragraph_coverage`
passes if `def x():` exists — even if the body is `pass`. Add a
fourth structural check:

```python
def _check_body_non_trivial(ast, python_source):
    # For each COBOL paragraph that had > 1 statement, the matching
    # Python function should have > 1 non-pass non-comment line.
```

This single check would have flipped `IF402M` from "PASS-ready" to
"FAIL" — which is the truth. Cost: ~40 LOC. Most important change in
this whole document, because right now the system is **lying about
how good its output is.**

### Optional Step F. ProLeap fallback (the big lever)
For paragraphs Stage 2 stubs even after A-D, run them through
ProLeap's Java parser via `jpype1`. We get a proper AST for the
unparseable fragment and emit Python from that. Cost: significant —
JVM dependency, deployment complexity, ~500 LOC of glue — but this is
the realistic path to ≥80 % real (not stubbed) function bodies. Defer
until after A-E are in.

## What this looks like as a chart

```
                Before A-E        After A-E (est.)    After F (est.)
PASS verdicts*       0 %             ~30-50 %             ~70-85 %
Stub-body funcs    10.5 %            ~5-7 %               ~2-3 %
"unparseable
  line" warnings    ~hundreds        ~tens                ~dozens
* given working API access
```

## What I'd do this week, in order

1. **Step E (verifier body-non-trivial check)** — 40 LOC, immediate
   honesty improvement. Stops the system from claiming PASS-ready on
   empty stubs.
2. **Step A (cobc preflight)** — confirms which programs are
   genuinely broken vs. parser-misunderstood. Cheap quality signal.
3. **Step B (regex normaliser R1 + R2 + R4)** — biggest single
   unstub win. Margins, intrinsic functions, AT END.
4. **Step C (Stingray PIC decoder)** — fix the data section once and
   correctness flows downstream.
5. **Step B continued (R5 + R6, INSPECT + OCCURS)** — covers the long
   tail of common verbs.
6. **Step D (legacylens diff)** — measures coverage so we know if
   A-C are working.
7. **Step F (ProLeap fallback)** — only if we're still under 80 %
   real conversion after the above.
