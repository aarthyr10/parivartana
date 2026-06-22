
from __future__ import annotations

import textwrap

import pytest

from src.evaluation.verifier import verify, _check_body_non_trivial
from src.pipeline.stage1_parser.cobc_preflight import (
    PreflightResult,
    cobc_preflight,
    is_cobc_available,
)
from src.pipeline.stage1_parser.normaliser import (
    NormaliserConfig,
    decode_intrinsic_functions,
    expand_inspect,
    mark_io_clauses,
    mark_occurs,
    normalise_cobol,
    parse_pic,
    strip_fixed_format_margins,
)
from src.pipeline.stage1_parser.parser import CobolParser
from src.pipeline.stage1_parser.pic_decoder import (
    PicDecoding,
    decode_pic,
    needed_imports_for,
)
from src.pipeline.stage1_parser.proleap_fallback import status as proleap_status


def test_body_non_trivial_flags_pass_stubs():
                                                                               
                                                                               
    cobol = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       DATA DIVISION.\n"
        "       WORKING-STORAGE SECTION.\n"
        "       01 X PIC 9(3) VALUE 0.\n"
        "       01 Y PIC 9(3) VALUE 0.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           MOVE 1 TO X.\n"
        "           DISPLAY X.\n"
        "           MOVE 2 TO Y.\n"
        "           PERFORM OTHER-PARA.\n"
        "           STOP RUN.\n"
        "       OTHER-PARA.\n"
        "           ADD 1 TO Y.\n"
        "           DISPLAY Y.\n"
        "           MOVE 5 TO Y.\n"
    )
    ast = CobolParser().parse(cobol).ast
    stub_py = (
        "def main_para():\n    x = 1\n    print(x)\n    y = 2\n    other_para()\n\n"
        "def other_para():\n    pass\n"
    )
    report = verify(
        cobol_source=cobol,
        python_source=stub_py,
        ast=ast,
        run_execution=False,
        run_llm_judge=False,
    )
    body = report.get("body_non_trivial")
    assert body.ran is True
    assert body.passed is False
    assert body.score == 0.5                             
    assert "OTHER-PARA" in body.extra["trivial"]
    assert report.verdict == "FAIL"


def test_body_non_trivial_exempts_single_statement_paragraphs():
                                                                    
                                                             
    cobol = (
        "       IDENTIFICATION DIVISION.\n"
        "       PROGRAM-ID. T.\n"
        "       PROCEDURE DIVISION.\n"
        "       MAIN-PARA.\n"
        "           DISPLAY \"HELLO\".\n"
        "           STOP RUN.\n"
        "       TRIVIAL-PARA.\n"
        "           CONTINUE.\n"
    )
    ast = CobolParser().parse(cobol).ast
    py = (
        "def main_para():\n    print('HELLO')\n\n"
        "def trivial_para():\n    pass\n"
    )
    report = verify(
        cobol_source=cobol,
        python_source=py,
        ast=ast,
        run_execution=False,
        run_llm_judge=False,
    )
    body = report.get("body_non_trivial")
    assert body.passed is True
    assert "TRIVIAL-PARA" in body.extra["exempt"]


def test_preflight_skipped_when_cobc_missing(monkeypatch):
    monkeypatch.setattr(
        "src.pipeline.stage1_parser.cobc_preflight.shutil.which",
        lambda _: None,
    )
    r = cobc_preflight("       IDENTIFICATION DIVISION.\n")
    assert r.available is False
    assert r.accepted is None
    assert r.status == "skipped"


def test_preflight_status_property():
    assert PreflightResult(available=False, accepted=None).status == "skipped"
    assert PreflightResult(available=True, accepted=True).status == "accepted"
    assert PreflightResult(available=True, accepted=False).status == "rejected"


def test_strip_fixed_format_margins_drops_seqnums_and_tags():
    src = "000100 IDENTIFICATION DIVISION.                                         IF4024.2\n"
    out = strip_fixed_format_margins(src)
    assert "IDENTIFICATION DIVISION" in out
                                                                   
                                                      
    assert "IF4024.2" not in out
                                                 
    assert all(len(ln) <= 72 for ln in out.splitlines())


def test_strip_fixed_format_handles_comment_and_continuation():
    src = (
        "000100*THIS IS A COMMENT                                         IF4024.2\n"
        "000200    DISPLAY                                                IF4024.2\n"
        "000300-    \"HELLO WORLD\".                                       IF4024.2\n"
    )
    out = strip_fixed_format_margins(src)
                     
    assert "THIS IS A COMMENT" not in out
                                            
    lines = out.strip().splitlines()
    assert any("DISPLAY" in ln and "HELLO" in ln for ln in lines)


def test_decode_intrinsic_functions_handles_length_log_max():
    src = (
        'IF FUNCTION LENGTH("ABC") = FUNCTION LENGTH("ABC") CONTINUE.\n'
        "COMPUTE X = FUNCTION LOG(Y).\n"
        "COMPUTE Z = FUNCTION MAX(A, B, C).\n"
    )
    out, imports = decode_intrinsic_functions(src)
    assert 'len("ABC")' in out
    assert "math.log(Y)" in out
    assert "max(A, B, C)" in out
    assert "math" in imports


def test_mark_io_clauses_preserves_not_qualifier():
    src = "READ FILE-X AT END PERFORM EOF-RTN NOT AT END PERFORM REC-RTN."
    out = mark_io_clauses(src)
    assert "__AT_END__" in out
    assert "__NOT_AT_END__" in out
                                                                    
    assert " AT END " not in out.replace("__AT_END__", "").replace("__NOT_AT_END__", "")


def test_expand_inspect_handles_tally_and_replace():
    src = (
        'INSPECT FIELD-A TALLYING COUNTER FOR ALL "X".\n'
        'INSPECT FIELD-B REPLACING ALL "X" BY "Y".\n'
    )
    out = expand_inspect(src)
    assert "__INSPECT_COUNT__" in out
    assert "__INSPECT_REPLACE__" in out


def test_mark_occurs_carries_index_name():
    src = "05 WS-TABLE PIC X(10) OCCURS 5 TIMES INDEXED BY WS-IDX."
    out = mark_occurs(src)
    assert "__OCCURS_5__" in out
    assert "INDEXED_BY_WS-IDX" in out


def test_normalise_cobol_top_level_pipes_everything():
                                                                           
                                                                           
    def _line(body: str) -> str:
        return body.ljust(72) + "IF4024.2\n"

    src = (
        _line("000100*COMMENT")                                             
        + _line("000200 PROCEDURE DIVISION.")
        + _line("000300 MAIN-PARA.")
        + _line("000400     IF FUNCTION LENGTH(X) > 5 CONTINUE.")
        + _line("000500     READ FILE-X AT END PERFORM EOF-RTN.")
    )
    r = normalise_cobol(src)
    assert "len(X)" in r.cobol
    assert "__AT_END__" in r.cobol
    assert "IF4024.2" not in r.cobol                       
    assert "COMMENT" not in r.cobol                              
    assert r.transforms_applied == [
        "R1_strip_margins",
        "R2_intrinsic_functions",
        "R4_io_clauses",
        "R5_inspect",
        "R6_occurs",
    ]


@pytest.mark.parametrize(
    "pic,expected_type,expected_scale",
    [
        ("PIC X(10)", "str", 0),
        ("PIC 9(5)", "int", 0),
        ("PIC 9(5)V99", "Decimal", 2),
        ("PIC S9(4) COMP-3", "Decimal", 0),
        ("PICTURE IS S9(7)V99 COMP-3", "Decimal", 2),
    ],
)
def test_decode_pic_returns_expected_type(pic, expected_type, expected_scale):
    d = decode_pic(pic)
    assert d is not None
    assert d.type == expected_type
    assert d.scale == expected_scale


def test_decode_pic_signed_carries_through():
    assert decode_pic("PIC S9(4) COMP-3").signed is True
    assert decode_pic("PIC 9(4)").signed is False


def test_pic_decoder_default_literals_are_valid_python():
    import ast

    for pic in [
        "PIC X(10)",
        "PIC 9(5)",
        "PIC 9(5)V99",
        "PIC S9(4) COMP-3",
        "PIC X(1)",
    ]:
        d = decode_pic(pic)
                                                                           
                                                  
        ns = "from decimal import Decimal\n"
        ast.parse(ns + d.default_literal)


def test_needed_imports_collects_decimal():
    decs = [decode_pic(p) for p in ["PIC X(10)", "PIC 9(5)V99", "PIC S9(4) COMP-3"]]
    decs = [d for d in decs if d]
    assert "decimal.Decimal" in needed_imports_for(decs)


def test_proleap_status_reports_missing_jpype_clearly(monkeypatch):
                                    
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "jpype":
            raise ImportError("forced for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    s = proleap_status()
    assert s.available is False
    assert "jpype1" in s.reason


def test_proleap_status_reports_missing_jar(monkeypatch, tmp_path):
                                                             
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "jpype":
            class Dummy:
                pass

            return Dummy()
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setenv("PARIVARTANA_PROLEAP_JAR", str(tmp_path / "missing.jar"))
    s = proleap_status()
    assert s.available is False
    assert "ProLeap jar not found" in s.reason
