from __future__ import annotations

from src.pipeline.stage3_llm.semantic_validator import (
    LexicalFallbackValidator,
    NliLabel,
    SemanticValidator,
)


def test_lexical_fallback_high_overlap_is_supported():
    val = LexicalFallbackValidator()
    res = val.check(
        "Compute the gross pay from hours worked and hourly rate.",
        "Compute gross pay from hours worked multiplied by hourly rate.",
    )
    assert res.label == NliLabel.SUPPORTED
    assert res.source == "lexical"
    assert 0.0 <= res.confidence <= 1.0


def test_lexical_fallback_low_overlap_is_refuted():
    val = LexicalFallbackValidator()
    res = val.check(
        "Compute the gross pay from hours worked.",
        "Render a customer dashboard widget in HTML.",
    )
    assert res.label == NliLabel.REFUTED


def test_lexical_fallback_partial_overlap_is_nei():
                                                                 
    val = LexicalFallbackValidator()
    res = val.check(
        "Compute gross pay from hours worked and rate.",
        "Compute net pay using hours and overtime rate.",
    )
    assert res.label == NliLabel.NEI


def test_empty_input_returns_nei():
    val = LexicalFallbackValidator()
    res = val.check("", "Compute something.")
    assert res.label == NliLabel.NEI
    assert res.confidence == 0.0


def test_validator_uses_lexical_fallback_when_hf_unavailable():
                                                                        
    val = SemanticValidator(
        model_name="parivartana/__definitely_not_a_real_model__",
        fallback_to_lexical=True,
    )
    res = val.check(
        "Move employee name from input to working storage.",
        "Copy employee name from input into working storage.",
    )
    assert res.source == "lexical"
    assert res.label in {NliLabel.SUPPORTED, NliLabel.NEI}
