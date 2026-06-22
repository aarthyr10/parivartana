from __future__ import annotations

import ast

from src.pipeline.stage1_parser.parser import CobolParser
from src.pipeline.stage2_neural.rule_based import RuleBasedTranslator

HELLO = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY "HELLO WORLD".
           STOP RUN.
"""

SUM_LOOP = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SUM-LOOP.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-COUNTER  PIC 9(3) VALUE 1.
       01 WS-LIMIT    PIC 9(3) VALUE 100.
       01 WS-TOTAL    PIC 9(7) VALUE 0.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM ADD-PARA UNTIL WS-COUNTER > WS-LIMIT.
           DISPLAY "TOTAL: " WS-TOTAL.
           STOP RUN.
       ADD-PARA.
           ADD WS-COUNTER TO WS-TOTAL.
           ADD 1 TO WS-COUNTER.
"""


def _parse_and_translate(source: str):
    parse = CobolParser().parse(source)
    assert parse.ok, parse.errors
    return RuleBasedTranslator().translate(parse.ast)


def test_hello_world_produces_valid_python():
    out = _parse_and_translate(HELLO)
                           
    ast.parse(out.code)
    assert 'print("HELLO WORLD")' in out.code
    assert "def main_para()" in out.code
    assert "main_para()" in out.code


def test_sum_loop_emits_state_dict_and_while_loop():
    out = _parse_and_translate(SUM_LOOP)
    ast.parse(out.code)
                                                   
    assert "'ws_counter'" in out.code
    assert "'ws_total'" in out.code
                                             
    assert "while not" in out.code
    assert "add_para()" in out.code


def test_identification_metadata_does_not_leak_as_paragraph():
    src = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO-WORLD.
       AUTHOR. AARTHY-RAMACHANDRAN.

       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY "HELLO WORLD".
           STOP RUN.
"""
    out = _parse_and_translate(src)
    ast.parse(out.code)
                                            
    assert "def aarthy_ramachandran" not in out.code
                                                       
    assert "def main_para()" in out.code
    entry_block = out.code.split('if __name__ == "__main__":')[-1]
    assert "main_para()" in entry_block
                                                                         
    from src.pipeline.stage1_parser.parser import CobolParser
    parse = CobolParser().parse(src)
    assert parse.ast.attributes.get("metadata", {}).get("author", "").upper().startswith("AARTHY")


def test_entry_point_prefers_main_named_paragraph():
    src = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. MIX.
       PROCEDURE DIVISION.
       INIT-PARA.
           DISPLAY "init".
       MAIN-PARA.
           DISPLAY "main".
           STOP RUN.
"""
    out = _parse_and_translate(src)
    ast.parse(out.code)
    entry_block = out.code.split('if __name__ == "__main__":')[-1]
    assert "main_para()" in entry_block
    assert "init_para()" not in entry_block


def test_unsupported_verb_emits_todo():
    from src.pipeline.stage2_neural import rule_based
    original = dict(rule_based._VERB_TABLE)
    rule_based._VERB_TABLE.pop("MOVE", None)
    try:
        src = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. WEIRD.
       PROCEDURE DIVISION.
       MAIN-PARA.
           MOVE 1 TO X.
           STOP RUN.
"""
        out = _parse_and_translate(src)
        assert any("MOVE" in w for w in out.warnings)
        assert "TODO" in out.code
    finally:
        rule_based._VERB_TABLE.clear()
        rule_based._VERB_TABLE.update(original)
