from __future__ import annotations

from src.evaluation.verifier import (
    VERDICT_FAIL,
    VERDICT_INCONCLUSIVE,
    verify,
)
from src.pipeline.stage1_parser.parser import CobolParser


HELLO_COBOL = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY "HELLO WORLD".
           STOP RUN.
"""


GOOD_PYTHON = '''\
def main_para() -> None:
    print("HELLO WORLD")

if __name__ == "__main__":
    main_para()
'''


BROKEN_PYTHON = "def main_para(:\n    pass"               


def _ast_for(src: str):
    return CobolParser().parse(src).ast


def test_passes_when_only_structural_checks_run():
                                                                           
    report = verify(
        cobol_source=HELLO_COBOL,
        python_source=GOOD_PYTHON,
        ast=_ast_for(HELLO_COBOL),
        run_execution=False,
        run_llm_judge=False,
    )
    syntax = report.get("python_syntax_valid")
    paragraph = report.get("paragraph_coverage")
    assert syntax.passed is True
    assert paragraph.passed is True
    assert paragraph.score == 1.0
    assert report.verdict == VERDICT_INCONCLUSIVE


def test_fails_on_python_syntax_error():
    report = verify(
        cobol_source=HELLO_COBOL,
        python_source=BROKEN_PYTHON,
        ast=_ast_for(HELLO_COBOL),
        run_execution=False,
        run_llm_judge=False,
    )
    assert report.verdict == VERDICT_FAIL
    assert report.get("python_syntax_valid").passed is False


def test_fails_when_paragraph_is_missing():
    no_main = 'print("HELLO")\n'
    report = verify(
        cobol_source=HELLO_COBOL,
        python_source=no_main,
        ast=_ast_for(HELLO_COBOL),
        run_execution=False,
        run_llm_judge=False,
    )
    para = report.get("paragraph_coverage")
    assert para.passed is False
    assert "MAIN-PARA" in para.extra["missing"]


def test_identifier_coverage_scores_partial_match():
    cobol_with_data = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAY.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-AMOUNT  PIC 9(5) VALUE 0.
       01 WS-RATE    PIC 9(5) VALUE 0.
       PROCEDURE DIVISION.
       MAIN.
           DISPLAY "X".
           STOP RUN.
"""
                                                                          
    py = "def main() -> None:\n    ws_amount = 1\n    print('x')\n"
    report = verify(
        cobol_source=cobol_with_data,
        python_source=py,
        ast=_ast_for(cobol_with_data),
        run_execution=False,
        run_llm_judge=False,
    )
    ident = report.get("identifier_coverage")
    assert 0.4 <= ident.score <= 0.6
                                                        
    assert ident.passed is False


def test_execution_check_skipped_when_no_gnu_cobol():
    report = verify(
        cobol_source=HELLO_COBOL,
        python_source=GOOD_PYTHON,
        ast=_ast_for(HELLO_COBOL),
        run_execution=True,
        run_llm_judge=False,
    )
    exec_check = report.get("execution_match")
    assert exec_check.ran is False
    assert "GnuCOBOL" in exec_check.skipped_reason


def test_llm_judge_skipped_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    report = verify(
        cobol_source=HELLO_COBOL,
        python_source=GOOD_PYTHON,
        ast=_ast_for(HELLO_COBOL),
        run_execution=False,
        run_llm_judge=True,
    )
    judge = report.get("llm_judge")
    assert judge.ran is False
    assert "API key" in judge.skipped_reason


def test_report_serialises_to_plain_dict():
    report = verify(
        cobol_source=HELLO_COBOL,
        python_source=GOOD_PYTHON,
        ast=_ast_for(HELLO_COBOL),
        run_execution=False,
        run_llm_judge=False,
    )
    payload = report.to_dict()
    assert payload["verdict"] in {"PASS", "FAIL", "INCONCLUSIVE"}
    assert isinstance(payload["checks"], list)
    assert all("name" in c and "ran" in c for c in payload["checks"])
