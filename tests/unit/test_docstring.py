from __future__ import annotations

from src.pipeline.stage1_parser.complexity import ComplexityTier
from src.pipeline.stage3_llm.docstring import (
    DocstringInsertion,
    annotate_high_tier,
    insert_docstrings,
)


def test_insert_docstrings_adds_one_per_function():
    code = "def foo():\n    pass\n\ndef bar():\n    return 1\n"
    out = insert_docstrings(
        code,
        [
            DocstringInsertion(function_name="foo", docstring="Do foo."),
            DocstringInsertion(function_name="bar", docstring="Do bar."),
        ],
    )
    assert '"""Do foo."""' in out
    assert '"""Do bar."""' in out


def test_insert_docstrings_is_idempotent_when_docstring_present():
    code = 'def foo():\n    """Existing."""\n    pass\n'
    out = insert_docstrings(code, [DocstringInsertion(function_name="foo", docstring="New.")])
    assert out.count('"""') == 2                          


def test_annotate_high_tier_only_for_high():
    assert annotate_high_tier("x = 1\n", ComplexityTier.SIMPLE) == "x = 1\n"
    assert "HUMAN REVIEW REQUIRED" in annotate_high_tier("x = 1\n", ComplexityTier.HIGH)


def test_annotate_high_tier_is_idempotent():
    once = annotate_high_tier("x = 1\n", ComplexityTier.HIGH)
    twice = annotate_high_tier(once, ComplexityTier.HIGH)
    assert once == twice
