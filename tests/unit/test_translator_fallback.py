
from __future__ import annotations

import ast

from src.pipeline.stage1_parser.complexity import ComplexityTier
from src.pipeline.stage1_parser.parser import CobolParser
from src.pipeline.stage2_neural.translator import NeuralTranslator

HELLO = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY "HI".
           STOP RUN.
"""


def test_translator_falls_back_to_rules_when_model_unavailable():
    parse = CobolParser().parse(HELLO)
    assert parse.ok

    translator = NeuralTranslator(
        model_name="parivartana/__definitely_not_a_real_model__",
        fallback_to_rules=True,
    )
    result = translator.translate(parse.ast, ComplexityTier.SIMPLE)

    assert result.metadata["fallback"] is True
    assert result.model_name == "rule-based-fallback"
    assert 'print("HI")' in result.python_code
    ast.parse(result.python_code)


def test_translator_records_inference_time():
    parse = CobolParser().parse(HELLO)
    translator = NeuralTranslator(
        model_name="parivartana/__definitely_not_a_real_model__",
        fallback_to_rules=True,
    )
    result = translator.translate(parse.ast, ComplexityTier.SIMPLE)
    assert result.inference_time_ms >= 0.0


def test_translator_raises_when_fallback_disabled():
    parse = CobolParser().parse(HELLO)
    translator = NeuralTranslator(
        model_name="parivartana/__definitely_not_a_real_model__",
        fallback_to_rules=False,
    )
    raised = False
    try:
        translator.translate(parse.ast, ComplexityTier.SIMPLE)
    except Exception:
        raised = True
    assert raised
