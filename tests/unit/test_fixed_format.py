from __future__ import annotations

from src.pipeline.stage1_parser.fixed_format import FixedFormatPreprocessor


def test_strips_sequence_area():
    pre = FixedFormatPreprocessor()
    line = "000100 IDENTIFICATION DIVISION."
    result = pre.preprocess(line)
    assert len(result) == 1
    assert result[0].sequence_area == "000100"
    assert "IDENTIFICATION DIVISION" in result[0].code


def test_detects_comment_lines():
    pre = FixedFormatPreprocessor()
    text = "000100*THIS IS A COMMENT"
    lines = pre.preprocess(text)
    assert lines[0].is_comment is True
    assert lines[0].code == ""


def test_detects_continuation_indicator():
    pre = FixedFormatPreprocessor()
    text = "000100-      'CONTINUED LITERAL'"
    lines = pre.preprocess(text)
    assert lines[0].is_continuation is True


def test_join_code_skips_comments():
    pre = FixedFormatPreprocessor()
    text = (
        "000100*HEADER COMMENT\n"
        "000200 PROGRAM-ID. SAMPLE.\n"
        "000300*ANOTHER COMMENT\n"
        "000400 STOP RUN."
    )
    lines = pre.preprocess(text)
    code = pre.join_code(lines)
    assert "HEADER COMMENT" not in code
    assert "PROGRAM-ID" in code
    assert "STOP RUN" in code
