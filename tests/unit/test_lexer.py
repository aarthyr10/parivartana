from __future__ import annotations

from src.pipeline.stage1_parser.lexer import CobolLexer, TokenType


def test_recognises_division_header():
    lex = CobolLexer()
    tokens = lex.tokenise("IDENTIFICATION DIVISION.")
    types = [t.type for t in tokens]
    assert TokenType.DIVISION_HEADER in types


def test_recognises_verbs():
    lex = CobolLexer()
    tokens = lex.tokenise("MOVE 5 TO WS-X.")
    verbs = [t for t in tokens if t.type == TokenType.VERB]
    assert verbs and verbs[0].value == "MOVE"


def test_recognises_string_literal():
    lex = CobolLexer()
    tokens = lex.tokenise('DISPLAY "HELLO".')
    strings = [t for t in tokens if t.type == TokenType.LITERAL_STR]
    assert strings and strings[0].value == "HELLO"


def test_recognises_numeric_literal():
    lex = CobolLexer()
    tokens = lex.tokenise("ADD 100 TO WS-COUNT.")
    nums = [t for t in tokens if t.type == TokenType.LITERAL_NUM]
    assert any(t.value == "100" for t in nums)


def test_recognises_pic_clause():
    lex = CobolLexer()
    tokens = lex.tokenise("01 WS-AMT PIC 9(5)V99.")
    pic_tokens = [t for t in tokens if t.type == TokenType.PIC_CLAUSE]
    assert pic_tokens
