from __future__ import annotations

from pathlib import Path

from src.pipeline.stage1_parser import CobolParser, ComplexityScorer, ComplexityTier

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "data" / "samples"


def _score(file_name: str):
    source = (SAMPLES / file_name).read_text(encoding="utf-8")
    result = CobolParser().parse(source)
    return ComplexityScorer().score(result.ast)


def test_hello_world_is_simple_tier():
    score = _score("hello_world.cob")
    assert score.tier == ComplexityTier.SIMPLE


def test_payroll_has_several_verbs():
    score = _score("payroll.cob")
    assert score.unique_verb_count >= 3


def test_sum_loop_has_cross_refs():
    score = _score("sum_loop.cob")
    assert score.cross_ref_count >= 1


def test_score_is_non_negative():
    for sample in ["hello_world.cob", "payroll.cob", "sum_loop.cob"]:
        score = _score(sample)
        assert score.raw_score >= 0
        assert score.ast_depth >= 1
