from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.pipeline.stage1_parser import (
    ComplexityScorer,
    ComplexityTier,
    CobolParser,
)


@dataclass
class ProcessedRow:
    id: str
    source: str
    tier: ComplexityTier
    complexity_score: float
    ast_depth: int
    unique_verb_count: int
    cross_ref_count: int
    high_tier_flag: int
    parse_ok: bool
    error_count: int


class CobolPreprocessor:
    def __init__(self) -> None:
        self.parser = CobolParser()
        self.scorer = ComplexityScorer()

    def process_record(self, rec: dict) -> ProcessedRow:
        source = rec.get("source", "")
        record_id = str(rec.get("id") or rec.get("instance_id") or "")
        result = self.parser.parse(source)

        if result.ok and result.ast is not None:
            score = self.scorer.score(result.ast)
            return ProcessedRow(
                id=record_id,
                source=source,
                tier=score.tier,
                complexity_score=score.raw_score,
                ast_depth=score.ast_depth,
                unique_verb_count=score.unique_verb_count,
                cross_ref_count=score.cross_ref_count,
                high_tier_flag=score.high_tier_flag,
                parse_ok=True,
                error_count=0,
            )

        return ProcessedRow(
            id=record_id,
            source=source,
            tier=ComplexityTier.HIGH,
            complexity_score=0.0,
            ast_depth=0,
            unique_verb_count=0,
            cross_ref_count=0,
            high_tier_flag=1,
            parse_ok=False,
            error_count=len(result.errors),
        )

    def process(self, records: Iterable[dict]) -> list[ProcessedRow]:
        return [self.process_record(rec) for rec in records]
