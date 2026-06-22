from __future__ import annotations

import math
from dataclasses import dataclass

from src.pipeline.stage1_parser.complexity import ComplexityTier


@dataclass
class CurriculumState:
    epoch: int
    current_tier: ComplexityTier
    plateau_count: int
    last_metric: float


class CurriculumScheduler:
    def __init__(
        self,
        plateau_epochs: int = 3,
        pacing: str = "exponential",
    ) -> None:
        self.plateau_epochs = plateau_epochs
        self.pacing = pacing
        self.state = CurriculumState(
            epoch=0,
            current_tier=ComplexityTier.SIMPLE,
            plateau_count=0,
            last_metric=0.0,
        )

    def step(self, validation_metric: float) -> ComplexityTier:
        delta = validation_metric - self.state.last_metric
        if delta < 1e-3:
            self.state.plateau_count += 1
        else:
            self.state.plateau_count = 0

        if self.state.plateau_count >= self.plateau_epochs:
            self._advance_tier()
            self.state.plateau_count = 0

        self.state.epoch += 1
        self.state.last_metric = validation_metric
        return self.state.current_tier

    def _advance_tier(self) -> None:
        order = [ComplexityTier.SIMPLE, ComplexityTier.MEDIUM, ComplexityTier.HIGH]
        idx = order.index(self.state.current_tier)
        if idx + 1 < len(order):
            self.state.current_tier = order[idx + 1]

    def sample_weights(self, sample_tiers: list[ComplexityTier]) -> list[float]:
        order = [ComplexityTier.SIMPLE, ComplexityTier.MEDIUM, ComplexityTier.HIGH]
        current_idx = order.index(self.state.current_tier)

        weights: list[float] = []
        for tier in sample_tiers:
            tier_idx = order.index(tier)
            if tier_idx > current_idx:
                weights.append(0.0)
            else:
                if self.pacing == "exponential":
                    weights.append(math.exp(-(current_idx - tier_idx)))
                else:
                    weights.append(1.0)
        return weights
