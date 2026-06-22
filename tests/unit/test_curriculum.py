from __future__ import annotations

from src.pipeline.stage1_parser.complexity import ComplexityTier
from src.pipeline.stage2_neural.curriculum import CurriculumScheduler


def test_starts_at_simple():
    sch = CurriculumScheduler()
    assert sch.state.current_tier == ComplexityTier.SIMPLE


def test_advances_after_plateau():
    sch = CurriculumScheduler(plateau_epochs=2)
                                                                          
                                 
    sch.step(0.5)
    sch.step(0.5)
    sch.step(0.5)
    assert sch.state.current_tier == ComplexityTier.MEDIUM


def test_does_not_advance_when_improving():
    sch = CurriculumScheduler(plateau_epochs=2)
    sch.step(0.1)
    sch.step(0.2)
    sch.step(0.3)
    sch.step(0.4)
    assert sch.state.current_tier == ComplexityTier.SIMPLE


def test_stays_at_high_once_reached():
    sch = CurriculumScheduler(plateau_epochs=1)
    for _ in range(20):
        sch.step(0.5)
    assert sch.state.current_tier == ComplexityTier.HIGH


def test_sample_weights_mask_future_tiers():
    sch = CurriculumScheduler()
    weights = sch.sample_weights(
        [ComplexityTier.SIMPLE, ComplexityTier.MEDIUM, ComplexityTier.HIGH]
    )
    assert weights[0] > 0
    assert weights[1] == 0.0
    assert weights[2] == 0.0
