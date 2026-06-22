
from __future__ import annotations

from src.pipeline.stage1_parser.complexity import ComplexityTier
from src.pipeline.stage2_neural.training import (
    CurriculumTrainer,
    ParallelExample,
    TrainingConfig,
)


def _examples(simple: int = 6, medium: int = 3, high: int = 1) -> list[ParallelExample]:
    out: list[ParallelExample] = []
    for i in range(simple):
        out.append(ParallelExample("", "", ComplexityTier.SIMPLE, source_id=f"s{i}"))
    for i in range(medium):
        out.append(ParallelExample("", "", ComplexityTier.MEDIUM, source_id=f"m{i}"))
    for i in range(high):
        out.append(ParallelExample("", "", ComplexityTier.HIGH, source_id=f"h{i}"))
    return out


def test_dry_run_returns_one_row_per_epoch():
    trainer = CurriculumTrainer(TrainingConfig(max_epochs=8, curriculum_plateau_epochs=2))
    metrics = [0.1, 0.2, 0.2, 0.2, 0.3, 0.3, 0.3, 0.4]
    history = trainer.dry_run(_examples(), metrics)
    assert len(history) == len(metrics)
    for i, row in enumerate(history, start=1):
        assert row["epoch"] == i
        assert row["active_tier"] in {"simple", "medium", "high"}
        assert 0 <= row["eligible_examples"] <= row["total_examples"]


def test_dry_run_advances_tier_on_plateau():
    trainer = CurriculumTrainer(TrainingConfig(curriculum_plateau_epochs=2))
                                                                                  
    history = trainer.dry_run(_examples(), [0.2, 0.2, 0.2, 0.2, 0.2])
    final_tier = history[-1]["active_tier"]
    assert final_tier in {"medium", "high"}


def test_dry_run_releases_more_examples_as_tier_advances():
    trainer = CurriculumTrainer(TrainingConfig(curriculum_plateau_epochs=1))
    history = trainer.dry_run(_examples(), [0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2])
                                                                         
                                              
    eligible = [row["eligible_examples"] for row in history]
    for prev, nxt in zip(eligible, eligible[1:]):
        assert nxt >= prev, f"eligible count decreased: {eligible}"


def test_dry_run_with_real_tier_distribution_from_preprocessor(tmp_path):
    from src.data.preprocess import CobolPreprocessor

    pre = CobolPreprocessor()
    sources = [
        ("hello", "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. HELLO.\n       PROCEDURE DIVISION.\n       MAIN.\n           DISPLAY \"HI\".\n           STOP RUN.\n"),
        ("loop", "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. LOOP.\n       PROCEDURE DIVISION.\n       MAIN.\n           PERFORM A UNTIL X > 1.\n           STOP RUN.\n       A.\n           ADD 1 TO X.\n"),
        ("calc", "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. CALC.\n       PROCEDURE DIVISION.\n       MAIN.\n           COMPUTE X = 1 + 2.\n           STOP RUN.\n"),
    ]
    examples = []
    for rec_id, src in sources:
        processed = pre.process_record({"id": rec_id, "source": src})
        assert processed.parse_ok
        examples.append(
            ParallelExample(
                source_prompt=processed.id,
                target_python="",
                tier=processed.tier,
                source_id=processed.id,
            )
        )

    trainer = CurriculumTrainer(TrainingConfig(curriculum_plateau_epochs=2))
    history = trainer.dry_run(examples, [0.1, 0.2, 0.2])
    assert len(history) == 3
    assert all(row["total_examples"] == 3 for row in history)
