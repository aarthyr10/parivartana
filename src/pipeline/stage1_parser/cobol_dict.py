
from __future__ import annotations


VERBS: frozenset[str] = frozenset({
    "ACCEPT", "ADD", "ALTER", "CALL", "CANCEL", "CLOSE", "COMPUTE",
    "CONTINUE", "DELETE", "DISPLAY", "DIVIDE", "ENTER", "EVALUATE",
    "EXIT", "GENERATE", "GO", "GOBACK", "IF", "INITIALIZE", "INITIATE",
    "INSPECT", "INVOKE", "MERGE", "MOVE", "MULTIPLY", "OPEN",
    "PERFORM", "READ", "RECEIVE", "RELEASE", "RETURN", "REWRITE",
    "SEARCH", "SEND", "SET", "SORT", "START", "STOP", "STRING",
    "SUBTRACT", "SUPPRESS", "TERMINATE", "UNSTRING", "USE", "WHEN",
    "WRITE", "ELSE",
})


KEYWORDS_DIVISION: frozenset[str] = frozenset({
    "IDENTIFICATION", "ENVIRONMENT", "DATA", "PROCEDURE", "DIVISION",
    "SECTION", "PROGRAM-ID", "AUTHOR", "INSTALLATION", "DATE-WRITTEN",
    "DATE-COMPILED", "SECURITY", "REMARKS",
    "CONFIGURATION", "SOURCE-COMPUTER", "OBJECT-COMPUTER", "SPECIAL-NAMES",
    "INPUT-OUTPUT", "FILE-CONTROL", "I-O-CONTROL",
    "FILE", "WORKING-STORAGE", "LOCAL-STORAGE", "LINKAGE", "REPORT",
    "COMMUNICATION", "SCREEN",
})


KEYWORDS_DATA_DESC: frozenset[str] = frozenset({
    "PIC", "PICTURE", "VALUE", "VALUES", "USAGE", "OCCURS", "REDEFINES",
    "RENAMES", "DEPENDING", "ON", "INDEXED", "ASCENDING", "DESCENDING",
    "KEY", "BLANK", "WHEN", "ZERO", "JUSTIFIED", "JUST", "SIGN",
    "LEADING", "TRAILING", "SEPARATE", "CHARACTER", "SYNCHRONIZED",
    "SYNC", "GLOBAL", "EXTERNAL", "POINTER", "BASED",
    "FILLER",
})


KEYWORDS_USAGE: frozenset[str] = frozenset({
    "COMP", "COMP-1", "COMP-2", "COMP-3", "COMP-4", "COMP-5",
    "COMPUTATIONAL", "COMPUTATIONAL-1", "COMPUTATIONAL-2",
    "COMPUTATIONAL-3", "COMPUTATIONAL-4", "COMPUTATIONAL-5",
    "BINARY", "PACKED-DECIMAL", "DISPLAY-1", "INDEX", "NATIONAL",
    "PROCEDURE-POINTER", "FUNCTION-POINTER", "OBJECT", "REFERENCE",
})


KEYWORDS_FILE: frozenset[str] = frozenset({
    "FD", "SD", "RD", "CD", "SELECT", "ASSIGN", "ORGANIZATION", "IS",
    "ACCESS", "MODE", "RECORD", "RECORDS", "KEY", "STATUS", "RESERVE",
    "AREAS", "ALTERNATE", "LABEL", "DATA", "RECORDING",
    "SEQUENTIAL", "RELATIVE", "INDEXED", "LINE", "RANDOM", "DYNAMIC",
    "OPTIONAL", "FILE-CONTROL", "I-O-CONTROL", "PADDING", "PASSWORD",
    "BLOCK", "CONTAINS", "STANDARD", "OMITTED", "EXTERNAL",
    "INPUT", "OUTPUT", "I-O", "EXTEND", "BEFORE", "AFTER", "ADVANCING",
    "PAGE", "LINES", "AT", "END", "INVALID", "FORMAT", "F", "V", "U",
})


KEYWORDS_PROC: frozenset[str] = frozenset({
    "TO", "FROM", "BY", "GIVING", "OF", "IN", "INTO", "USING", "RUN",
    "PROGRAM", "VARYING", "UNTIL", "TIMES", "THRU", "THROUGH",
    "RETURNING", "REPLACING", "ALL", "LEADING", "FIRST", "TRAILING",
    "TALLYING", "CHARACTERS", "INITIAL", "BEFORE", "AFTER",
    "DELIMITED", "POINTER", "COUNT", "WITH", "TEST", "ADVANCING",
    "ANY", "OTHER", "REFERENCE", "CONTENT", "OMITTED",
    "CORRESPONDING", "CORR", "AS", "TIME", "DATE", "DAY", "DAY-OF-WEEK",
    "EXCEPTION", "OVERFLOW", "SIZE", "ERROR",
})


KEYWORDS_END: frozenset[str] = frozenset({
    "END-IF", "END-PERFORM", "END-EVALUATE", "END-READ", "END-WRITE",
    "END-COMPUTE", "END-ADD", "END-SUBTRACT", "END-MULTIPLY",
    "END-DIVIDE", "END-CALL", "END-DELETE", "END-RETURN", "END-REWRITE",
    "END-SEARCH", "END-START", "END-STRING", "END-UNSTRING",
    "END-DISPLAY", "END-ACCEPT", "END-INVOKE", "END-RECEIVE", "END-SEND",
})


KEYWORDS_COND: frozenset[str] = frozenset({
    "IS", "ARE", "NOT", "AND", "OR", "EQUAL", "EQUALS", "GREATER",
    "LESS", "THAN", "OR", "EQUAL", "NEGATIVE", "POSITIVE", "ZERO",
    "NUMERIC", "ALPHABETIC", "ALPHABETIC-LOWER", "ALPHABETIC-UPPER",
    "ALPHANUMERIC", "ALPHANUMERIC-EDITED", "NUMERIC-EDITED",
    "TRUE", "FALSE", "ALSO", "WHEN", "ANY", "OTHER", "TO",
    "THEN",
})


FIGURATIVE: frozenset[str] = frozenset({
    "ZERO", "ZEROS", "ZEROES", "SPACE", "SPACES",
    "HIGH-VALUE", "HIGH-VALUES", "LOW-VALUE", "LOW-VALUES",
    "QUOTE", "QUOTES", "NULL", "NULLS", "ALL",
})


ALL_RESERVED: frozenset[str] = (
    VERBS
    | KEYWORDS_DIVISION
    | KEYWORDS_DATA_DESC
    | KEYWORDS_USAGE
    | KEYWORDS_FILE
    | KEYWORDS_PROC
    | KEYWORDS_END
    | KEYWORDS_COND
    | FIGURATIVE
)


VERB_GRAMMAR: dict[str, dict] = {
    "MOVE":       {"takes_target": True,  "connectors": {"TO"},                       "end_scope": None},
    "ADD":        {"takes_target": True,  "connectors": {"TO", "GIVING"},             "end_scope": "END-ADD"},
    "SUBTRACT":   {"takes_target": True,  "connectors": {"FROM", "GIVING"},           "end_scope": "END-SUBTRACT"},
    "MULTIPLY":   {"takes_target": True,  "connectors": {"BY", "GIVING"},             "end_scope": "END-MULTIPLY"},
    "DIVIDE":     {"takes_target": True,  "connectors": {"INTO", "BY", "GIVING"},     "end_scope": "END-DIVIDE"},
    "COMPUTE":    {"takes_target": True,  "connectors": {"="},                        "end_scope": "END-COMPUTE"},
    "DISPLAY":    {"takes_target": False, "connectors": {"UPON", "WITH", "NO", "ADVANCING"}, "end_scope": "END-DISPLAY"},
    "ACCEPT":     {"takes_target": True,  "connectors": {"FROM"},                     "end_scope": "END-ACCEPT"},
    "PERFORM":    {"takes_target": True,  "connectors": {"UNTIL", "TIMES", "VARYING", "THRU", "THROUGH", "BY", "FROM"}, "end_scope": "END-PERFORM"},
    "STOP":       {"takes_target": False, "connectors": {"RUN"},                      "end_scope": None},
    "GOBACK":     {"takes_target": False, "connectors": set(),                        "end_scope": None},
    "EXIT":       {"takes_target": False, "connectors": {"PROGRAM", "PERFORM"},       "end_scope": None},
    "CONTINUE":   {"takes_target": False, "connectors": set(),                        "end_scope": None},
    "IF":         {"takes_target": False, "connectors": {"THEN"},                     "end_scope": "END-IF"},
    "ELSE":       {"takes_target": False, "connectors": set(),                        "end_scope": "END-IF"},
    "EVALUATE":   {"takes_target": False, "connectors": {"ALSO", "WHEN", "OTHER"},    "end_scope": "END-EVALUATE"},
    "WHEN":       {"takes_target": False, "connectors": set(),                        "end_scope": "END-EVALUATE"},
    "INITIALIZE": {"takes_target": True,  "connectors": {"REPLACING", "ALL", "BY"},   "end_scope": None},
    "CALL":       {"takes_target": True,  "connectors": {"USING", "RETURNING", "BY", "REFERENCE", "CONTENT"}, "end_scope": "END-CALL"},
    "STRING":     {"takes_target": True,  "connectors": {"INTO", "DELIMITED", "POINTER", "WITH"}, "end_scope": "END-STRING"},
    "UNSTRING":   {"takes_target": True,  "connectors": {"INTO", "DELIMITED", "POINTER", "TALLYING", "COUNT"}, "end_scope": "END-UNSTRING"},
    "INSPECT":    {"takes_target": True,  "connectors": {"TALLYING", "REPLACING", "ALL", "LEADING", "FIRST", "CHARACTERS"}, "end_scope": None},
    "OPEN":       {"takes_target": True,  "connectors": {"INPUT", "OUTPUT", "I-O", "EXTEND"}, "end_scope": None},
    "CLOSE":      {"takes_target": True,  "connectors": set(),                        "end_scope": None},
    "READ":       {"takes_target": True,  "connectors": {"INTO", "AT", "END", "INVALID", "KEY", "NEXT"}, "end_scope": "END-READ"},
    "WRITE":      {"takes_target": True,  "connectors": {"FROM", "AFTER", "BEFORE", "ADVANCING", "INVALID", "KEY"}, "end_scope": "END-WRITE"},
    "REWRITE":    {"takes_target": True,  "connectors": {"FROM", "INVALID", "KEY"},   "end_scope": "END-REWRITE"},
    "DELETE":     {"takes_target": True,  "connectors": {"INVALID", "KEY"},           "end_scope": "END-DELETE"},
    "START":      {"takes_target": True,  "connectors": {"KEY", "INVALID"},           "end_scope": "END-START"},
    "RETURN":     {"takes_target": True,  "connectors": {"INTO", "AT", "END"},        "end_scope": "END-RETURN"},
    "RELEASE":    {"takes_target": True,  "connectors": {"FROM"},                     "end_scope": None},
    "SORT":       {"takes_target": True,  "connectors": {"ON", "ASCENDING", "DESCENDING", "KEY", "USING", "GIVING"}, "end_scope": None},
    "MERGE":      {"takes_target": True,  "connectors": {"ON", "ASCENDING", "DESCENDING", "KEY", "USING", "GIVING"}, "end_scope": None},
    "SET":        {"takes_target": True,  "connectors": {"TO", "UP", "DOWN", "BY"},   "end_scope": None},
    "GO":         {"takes_target": True,  "connectors": {"TO", "DEPENDING", "ON"},    "end_scope": None},
    "SEARCH":     {"takes_target": True,  "connectors": {"ALL", "VARYING", "WHEN", "AT", "END"}, "end_scope": "END-SEARCH"},
    "USE":        {"takes_target": False, "connectors": {"AFTER", "STANDARD", "EXCEPTION", "ERROR", "PROCEDURE"}, "end_scope": None},
    "ALTER":      {"takes_target": True,  "connectors": {"TO", "PROCEED"},            "end_scope": None},
    "CANCEL":     {"takes_target": True,  "connectors": set(),                        "end_scope": None},
}


def is_reserved(word: str) -> bool:
    return word.upper() in ALL_RESERVED


def is_verb(word: str) -> bool:
    return word.upper() in VERBS


def is_end_scope(word: str) -> bool:
    return word.upper() in KEYWORDS_END


def is_figurative(word: str) -> bool:
    return word.upper() in FIGURATIVE


def verb_grammar(word: str) -> dict | None:
    return VERB_GRAMMAR.get(word.upper())
