
from __future__ import annotations

import re
from dataclasses import dataclass, field


_FIXED_FORMAT_LINE = re.compile(r"^.{0,72}", re.MULTILINE)


def strip_fixed_format_margins(source: str) -> str:
    out_lines: list[str] = []
    for raw in source.splitlines():
                                                                     
        if len(raw) < 7:
            out_lines.append(raw)
            continue
        indicator = raw[6]
        if indicator == "*":
                                           
            continue
        if indicator == "/":
                                
            continue
                                                                      
        body = raw[:72]
        if indicator == "-" and out_lines:
                                                                         
            cont_body = raw[7:72].lstrip()
            out_lines[-1] = out_lines[-1].rstrip() + cont_body
        else:
            out_lines.append(body)
    return "\n".join(out_lines)


_INTRINSIC_MAP = {
    "LENGTH":     ("len({0})",                                      ()),
    "LOG":        ("math.log({0})",                                 ("math",)),
    "LOG10":      ("math.log10({0})",                               ("math",)),
    "MAX":        ("max({all})",                                    ()),
    "MIN":        ("min({all})",                                    ()),
    "MEAN":       ("statistics.mean([{all}])",                      ("statistics",)),
    "MEDIAN":     ("statistics.median([{all}])",                    ("statistics",)),
    "MIDRANGE":   ("((max({all}) + min({all})) / 2)",               ()),
    "MOD":        ("({0} % {1})",                                   ()),
    "REM":        ("math.fmod({0}, {1})",                           ("math",)),
    "NUMVAL":     ("float({0})",                                    ()),
    "NUMVAL-C":   ("float(str({0}).strip('$,'))",                   ()),
    "LOWER-CASE": ("{0}.lower()",                                   ()),
    "UPPER-CASE": ("{0}.upper()",                                   ()),
    "REVERSE":    ("{0}[::-1]",                                     ()),
    "TRIM":       ("{0}.strip()",                                   ()),
    "ORD":        ("ord({0})",                                      ()),
    "CHAR":       ("chr({0})",                                      ()),
    "ABS":        ("abs({0})",                                      ()),
    "SQRT":       ("math.sqrt({0})",                                ("math",)),
    "INTEGER":    ("int({0})",                                      ()),
    "INTEGER-PART": ("int({0})",                                    ()),
    "RANDOM":     ("random.random()",                               ("random",)),
                                                        
    "SIN":        ("math.sin({0})",                                 ("math",)),
    "COS":        ("math.cos({0})",                                 ("math",)),
    "TAN":        ("math.tan({0})",                                 ("math",)),
    "ASIN":       ("math.asin({0})",                                ("math",)),
    "ACOS":       ("math.acos({0})",                                ("math",)),
    "ATAN":       ("math.atan({0})",                                ("math",)),
    "EXP":        ("math.exp({0})",                                 ("math",)),
    "EXP10":      ("(10 ** {0})",                                   ()),
    "PI":         ("math.pi",                                       ("math",)),
    "E":          ("math.e",                                        ("math",)),
                                                                        
    "CURRENT-DATE": ("__import__('datetime').datetime.now().strftime('%Y%m%d%H%M%S00+0000')",  ()),
    "WHEN-COMPILED": ("__import__('datetime').datetime.now().strftime('%Y%m%d%H%M%S00')", ()),
    "DATE-OF-INTEGER": (
        "(__import__('datetime').date(1601,1,1)+__import__('datetime').timedelta(days={0}-1)).strftime('%Y%m%d')",
        (),
    ),
    "DATE-TO-YYYYMMDD": ("int({0})",                                ()),
    "DAY-OF-INTEGER": (
        "(__import__('datetime').date(1601,1,1)+__import__('datetime').timedelta(days={0}-1)).strftime('%Y%j')",
        (),
    ),
    "DAY-TO-YYYYDDD": ("int({0})",                                  ()),
    "INTEGER-OF-DATE": ("int({0})",                                 ()),
    "INTEGER-OF-DAY":  ("int({0})",                                 ()),
    "YEAR-TO-YYYY":    ("(2000 + {0}) if {0} < 50 else (1900 + {0})", ()),
                                 
    "FACTORIAL":   ("math.factorial(int({0}))",                     ("math",)),
    "SUM":         ("sum([{all}])",                                 ()),
    "STORED-CHAR-LENGTH": ("len(str({0}).rstrip())",                ()),
    "TEST-NUMVAL": ("(0 if str({0}).strip().replace('.','',1).lstrip('+-').isdigit() else 1)", ()),
    "TEST-NUMVAL-C": ("(0 if str({0}).strip('$,').replace('.','',1).lstrip('+-').isdigit() else 1)", ()),
}
_INTRINSIC_PATTERN = re.compile(
    r"\bFUNCTION\s+([A-Z\-]+)\s*\(([^()]*)\)",
    re.IGNORECASE,
)


def decode_intrinsic_functions(source: str) -> tuple[str, set[str]]:
    needed_imports: set[str] = set()

    def repl(m: re.Match) -> str:
        name = m.group(1).upper()
        args_raw = m.group(2).strip()
        if name not in _INTRINSIC_MAP:
            return m.group(0)
        template, imports = _INTRINSIC_MAP[name]
        for imp in imports:
            needed_imports.add(imp)
        args = [a.strip() for a in args_raw.split(",") if a.strip()] if args_raw else []
        try:
            return template.format(
                *args,
                all=", ".join(args),
            )
        except (IndexError, KeyError):
                                                                
                                                   
            return m.group(0)

    out = source
    for _ in range(3):
        new = _INTRINSIC_PATTERN.sub(repl, out)
        if new == out:
            break
        out = new
    return out, needed_imports


@dataclass
class PicInfo:

    raw: str
    is_numeric: bool
    is_signed: bool
    integer_digits: int = 0
    fractional_digits: int = 0
    char_length: int = 0
    usage: str = "DISPLAY"                                                     


_PIC_RE = re.compile(
    r"""PIC(?:TURE)?\s+(?:IS\s+)?                    # PIC, PICTURE, PIC IS, PICTURE IS
        (?P<sign>S?)                                  # optional S sign
        (?P<mask>(?:9|X|A|Z|V|,|\.|\(|\)|\d|/)+)      # full picture mask (no S here)
        (?:\s+(?P<usage>COMP-3|COMP-5|COMP|PACKED-DECIMAL|DISPLAY|BINARY))?
    """,
    re.IGNORECASE | re.VERBOSE,
)

                                                                     
_BARE_PIC_RE = re.compile(
    r"""^\s*(?P<sign>S?)
        (?P<mask>(?:9|X|A|Z|V|,|\.|\(|\)|\d|/)+)
        (?:\s+(?P<usage>COMP-3|COMP-5|COMP|PACKED-DECIMAL|DISPLAY|BINARY))?\s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def parse_pic(picture: str) -> PicInfo | None:
    m = _PIC_RE.search(picture)
    if not m:
                                                                        
                                    
        m = _BARE_PIC_RE.match(picture)
    if not m:
        return None
    sign = (m.group("sign") or "").upper() == "S"
    mask = (m.group("mask") or "").upper()
    usage = (m.group("usage") or "DISPLAY").upper().replace("PACKED-DECIMAL", "COMP-3")

                                                 
    def expand_repeats(s: str) -> str:
        return re.sub(r"([9XAZ])\((\d+)\)", lambda r: r.group(1) * int(r.group(2)), s)

    expanded = expand_repeats(mask)
    integer_digits = 0
    fractional_digits = 0
    char_length = 0
    is_numeric = "9" in expanded or "Z" in expanded
    if is_numeric:
        if "V" in expanded:
            int_part, frac_part = expanded.split("V", 1)
            integer_digits = int_part.count("9") + int_part.count("Z")
            fractional_digits = frac_part.count("9") + frac_part.count("Z")
        else:
            integer_digits = expanded.count("9") + expanded.count("Z")
    else:
        char_length = expanded.count("X") + expanded.count("A")
    return PicInfo(
        raw=mask,
        is_numeric=is_numeric,
        is_signed=sign,
        integer_digits=integer_digits,
        fractional_digits=fractional_digits,
        char_length=char_length,
        usage=usage,
    )


_AT_END_RE = re.compile(r"\bAT\s+END\b", re.IGNORECASE)
_NOT_AT_END_RE = re.compile(r"\bNOT\s+AT\s+END\b", re.IGNORECASE)
_INVALID_KEY_RE = re.compile(r"\bINVALID\s+KEY\b", re.IGNORECASE)
_NOT_INVALID_KEY_RE = re.compile(r"\bNOT\s+INVALID\s+KEY\b", re.IGNORECASE)


def mark_io_clauses(source: str) -> str:
    out = _NOT_AT_END_RE.sub("__NOT_AT_END__", source)
    out = _AT_END_RE.sub("__AT_END__", out)
    out = _NOT_INVALID_KEY_RE.sub("__NOT_INVALID_KEY__", out)
    out = _INVALID_KEY_RE.sub("__INVALID_KEY__", out)
    return out


_INSPECT_TALLY = re.compile(
    r'INSPECT\s+([A-Z][A-Z0-9\-]*)\s+TALLYING\s+([A-Z][A-Z0-9\-]*)\s+FOR\s+ALL\s+"([^"]+)"',
    re.IGNORECASE,
)
_INSPECT_REPLACE = re.compile(
    r'INSPECT\s+([A-Z][A-Z0-9\-]*)\s+REPLACING\s+ALL\s+"([^"]+)"\s+BY\s+"([^"]+)"',
    re.IGNORECASE,
)


def expand_inspect(source: str) -> str:
    out = _INSPECT_TALLY.sub(
        lambda m: f'COMPUTE {m.group(2)} = {m.group(2)} + __INSPECT_COUNT__({m.group(1)}, "{m.group(3)}")',
        source,
    )
    out = _INSPECT_REPLACE.sub(
        lambda m: f'MOVE __INSPECT_REPLACE__({m.group(1)}, "{m.group(2)}", "{m.group(3)}") TO {m.group(1)}',
        out,
    )
    return out


_OCCURS_RE = re.compile(
    r"OCCURS\s+(\d+)\s+TIMES(?:\s+INDEXED\s+BY\s+([A-Z][A-Z0-9\-]*))?",
    re.IGNORECASE,
)


def mark_occurs(source: str) -> str:
    return _OCCURS_RE.sub(
        lambda m: f"__OCCURS_{m.group(1)}__"
        + (f"_INDEXED_BY_{m.group(2)}" if m.group(2) else ""),
        source,
    )


@dataclass
class NormaliserConfig:
    strip_margins: bool = True           
    decode_intrinsics: bool = True       
    mark_io_clauses: bool = True         
    expand_inspect: bool = True          
    mark_occurs: bool = True             
                                                                    
                                                                     
@dataclass
class NormaliseResult:
    cobol: str
    needed_imports: set[str] = field(default_factory=set)
    transforms_applied: list[str] = field(default_factory=list)


def normalise_cobol(
    source: str,
    config: NormaliserConfig | None = None,
) -> NormaliseResult:
    cfg = config or NormaliserConfig()
    out = source
    imports: set[str] = set()
    applied: list[str] = []

    if cfg.strip_margins:
        out = strip_fixed_format_margins(out)
        applied.append("R1_strip_margins")
    if cfg.decode_intrinsics:
        out, imps = decode_intrinsic_functions(out)
        imports |= imps
        applied.append("R2_intrinsic_functions")
    if cfg.mark_io_clauses:
        out = mark_io_clauses(out)
        applied.append("R4_io_clauses")
    if cfg.expand_inspect:
        out = expand_inspect(out)
        applied.append("R5_inspect")
    if cfg.mark_occurs:
        out = mark_occurs(out)
        applied.append("R6_occurs")

    return NormaliseResult(cobol=out, needed_imports=imports, transforms_applied=applied)
