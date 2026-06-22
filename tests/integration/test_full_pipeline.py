
from __future__ import annotations

import ast

from src.pipeline.stage1_parser.complexity import ComplexityScorer
from src.pipeline.stage1_parser.parser import CobolParser
from src.pipeline.stage2_neural.translator import NeuralTranslator
from src.pipeline.stage3_llm.providers import LLMProvider, LLMResponse
from src.pipeline.stage3_llm.refiner import LLMRefiner


PAYROLL = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PAYROLL-CALC.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-HOURS-WORKED  PIC 9(3) VALUE 0.
       01 WS-HOURLY-RATE   PIC 9(3)V99 VALUE 0.
       01 WS-GROSS-PAY     PIC 9(6)V99 VALUE 0.
       PROCEDURE DIVISION.
       MAIN-PARA.
           MOVE 40 TO WS-HOURS-WORKED.
           MOVE 25.00 TO WS-HOURLY-RATE.
           COMPUTE WS-GROSS-PAY = WS-HOURS-WORKED * WS-HOURLY-RATE.
           DISPLAY "GROSS PAY: " WS-GROSS-PAY.
           STOP RUN.
"""


class _NoopProvider(LLMProvider):
    name = "noop"

    def is_available(self) -> bool:                                         
        return False

    def complete(self, system: str, user: str) -> LLMResponse:                    
        raise RuntimeError("should not be called when is_available() is False")


def test_full_pipeline_end_to_end():
                              
    parse = CobolParser().parse(PAYROLL)
    assert parse.ok, parse.errors
    score = ComplexityScorer().score(parse.ast)
    assert score.tier is not None

                                                         
    translator = NeuralTranslator(
        model_name="parivartana/__definitely_not_a_real_model__",
        fallback_to_rules=True,
    )
    translation = translator.translate(parse.ast, score.tier)
    assert translation.metadata["fallback"] is True
    ast.parse(translation.python_code)

                                                                      
    refiner = LLMRefiner(provider=_NoopProvider(model="noop"))
    identifiers = ["WS-HOURS-WORKED", "WS-HOURLY-RATE", "WS-GROSS-PAY"]
    result = refiner.refine(
        raw_python=translation.python_code,
        tier=score.tier,
        cobol_identifiers=identifiers,
        cobol_comment="Calculate gross pay from hours worked and hourly rate.",
        run_semantic_check=True,
        run_docstring_synthesis=False,
    )

                                                                      
    steps = result.metadata["pipeline_steps"]
    assert any(s.startswith("rename:") for s in steps)
    assert "llm_refine:no_provider" in steps
    assert any(s.startswith("semantic:") for s in steps)
                                                 
    ast.parse(result.refined_python)
