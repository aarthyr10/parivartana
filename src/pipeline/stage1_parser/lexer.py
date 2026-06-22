from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class TokenType(str, Enum):
    DIVISION_HEADER = "DIVISION_HEADER"
    SECTION_HEADER = "SECTION_HEADER"
    PARAGRAPH_NAME = "PARAGRAPH_NAME"
    LEVEL_NUMBER = "LEVEL_NUMBER"
    PIC_CLAUSE = "PIC_CLAUSE"
    VALUE_CLAUSE = "VALUE_CLAUSE"
    USAGE_CLAUSE = "USAGE_CLAUSE"
    VERB = "VERB"
    KEYWORD = "KEYWORD"
    IDENTIFIER = "IDENTIFIER"
    LITERAL_NUM = "LITERAL_NUM"
    LITERAL_STR = "LITERAL_STR"
    OPERATOR = "OPERATOR"
    PERIOD = "PERIOD"
    COMMA = "COMMA"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    EOF = "EOF"


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int


from src.pipeline.stage1_parser.cobol_dict import (
    VERBS as _DICT_VERBS,
    ALL_RESERVED as _DICT_ALL_RESERVED,
)


COBOL_VERBS = _DICT_VERBS

COBOL_KEYWORDS = _DICT_ALL_RESERVED - _DICT_VERBS

OPERATORS = {"+", "-", "*", "/", "=", "<", ">", "<=", ">=", "<>"}


_PIC_RE = re.compile(r"^(PIC|PICTURE)$", re.IGNORECASE)
_LEVEL_RE = re.compile(r"^(0[1-9]|[1-4][0-9]|66|77|88)$")
_NUM_LITERAL_RE = re.compile(r"^[+-]?\d+(\.\d+)?$")
_IDENT_RE = re.compile(r"^[A-Z][A-Z0-9-]*$", re.IGNORECASE)
_PIC_VALUE_RE = re.compile(r"^[9XAVSP()0-9V/.,+\-*$Z]+$", re.IGNORECASE)


class CobolLexer:
    def __init__(self) -> None:
        self._tokens: list[Token] = []

    def tokenise(self, source: str) -> list[Token]:
        tokens: list[Token] = []
        for line_no, raw_line in enumerate(source.splitlines(), start=1):
            tokens.extend(self._tokenise_line(raw_line, line_no))
        tokens.append(Token(TokenType.EOF, "", line=line_no if tokens else 1, column=0))
        self._tokens = tokens
        return tokens

    def _tokenise_line(self, line: str, line_no: int) -> list[Token]:
        out: list[Token] = []
        col = 0
        n = len(line)
        i = 0
        upper = line.upper()
        prev_was_pic = False

        while i < n:
            ch = line[i]
            if ch.isspace():
                i += 1
                continue

            if ch == ".":
                out.append(Token(TokenType.PERIOD, ".", line_no, i))
                i += 1
                prev_was_pic = False
                continue

            if ch == ",":
                out.append(Token(TokenType.COMMA, ",", line_no, i))
                i += 1
                continue

            if ch == "(":
                out.append(Token(TokenType.LPAREN, "(", line_no, i))
                i += 1
                continue
            if ch == ")":
                out.append(Token(TokenType.RPAREN, ")", line_no, i))
                i += 1
                continue

            if ch in {'"', "'"}:
                end = line.find(ch, i + 1)
                if end == -1:
                    end = n
                value = line[i + 1 : end]
                out.append(Token(TokenType.LITERAL_STR, value, line_no, i))
                i = end + 1
                continue

            j = i
            while j < n and not line[j].isspace() and line[j] not in {".", ",", "(", ")"}:
                j += 1
            word = line[i:j]
            word_upper = upper[i:j]

            if prev_was_pic and _PIC_VALUE_RE.match(word):
                out.append(Token(TokenType.PIC_CLAUSE, word, line_no, i))
                prev_was_pic = False
                i = j
                continue

            if _PIC_RE.match(word_upper):
                out.append(Token(TokenType.KEYWORD, word_upper, line_no, i))
                prev_was_pic = True
                i = j
                continue

            if _NUM_LITERAL_RE.match(word):
                if _LEVEL_RE.match(word) and self._at_data_position(out):
                    out.append(Token(TokenType.LEVEL_NUMBER, word, line_no, i))
                else:
                    out.append(Token(TokenType.LITERAL_NUM, word, line_no, i))
                i = j
                continue

            if word in OPERATORS:
                out.append(Token(TokenType.OPERATOR, word, line_no, i))
                i = j
                continue

            if word_upper.endswith("DIVISION"):
                out.append(Token(TokenType.DIVISION_HEADER, word_upper, line_no, i))
                i = j
                continue

            if word_upper.endswith("SECTION") and word_upper != "SECTION":
                out.append(Token(TokenType.SECTION_HEADER, word_upper, line_no, i))
                i = j
                continue

            if word_upper in COBOL_VERBS:
                out.append(Token(TokenType.VERB, word_upper, line_no, i))
                i = j
                continue

            if word_upper in COBOL_KEYWORDS:
                out.append(Token(TokenType.KEYWORD, word_upper, line_no, i))
                i = j
                continue

            if _IDENT_RE.match(word):
                out.append(Token(TokenType.IDENTIFIER, word, line_no, i))
                i = j
                continue

            i = j

        return out

    @staticmethod
    def _at_data_position(tokens: list[Token]) -> bool:
        if not tokens:
            return True
        last = tokens[-1]
        return last.type == TokenType.PERIOD or last.type == TokenType.SECTION_HEADER
