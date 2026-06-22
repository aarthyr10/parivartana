from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.pipeline.stage1_parser.ast_nodes import AstNode, StatementNode

HIGH_TIER_VERBS = frozenset(
    {
        "ALTER",
        "GO",
        "SORT",
        "MERGE",
        "REDEFINES",
    }
)

HIGH_TIER_KEYWORDS = frozenset(
    {
        "OCCURS",
        "DEPENDING",
        "EXEC",
        "POINTER",
        "REPORT",
    }
)


class ComplexityTier(str, Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class ComplexityScore:
    ast_depth: int
    unique_verb_count: int
    cross_ref_count: int
    high_tier_flag: int
    raw_score: float
    tier: ComplexityTier


class ComplexityScorer:
    def __init__(
        self,
        weights: dict | None = None,
        thresholds: dict | None = None,
    ) -> None:
        self.weights = weights or {
            "ast_depth": 0.35,
            "unique_verb_count": 0.25,
            "cross_ref_count": 0.25,
            "high_tier_flag": 0.15,
        }
        self.thresholds = thresholds or {"simple_max": 12, "medium_max": 28}

    def score(self, ast: AstNode) -> ComplexityScore:
        depth = ast.depth()
        verbs = self._unique_verbs(ast)
        cross_refs = self._count_cross_refs(ast)
        high_flag = self._has_high_tier_construct(ast)

        raw = (
            depth * self.weights["ast_depth"]
            + len(verbs) * self.weights["unique_verb_count"]
            + cross_refs * self.weights["cross_ref_count"]
            + (high_flag * 30) * self.weights["high_tier_flag"]
        )

        tier = self._assign_tier(raw)
        return ComplexityScore(
            ast_depth=depth,
            unique_verb_count=len(verbs),
            cross_ref_count=cross_refs,
            high_tier_flag=high_flag,
            raw_score=round(raw, 2),
            tier=tier,
        )

    def _assign_tier(self, raw: float) -> ComplexityTier:
        if raw <= self.thresholds["simple_max"]:
            return ComplexityTier.SIMPLE
        if raw <= self.thresholds["medium_max"]:
            return ComplexityTier.MEDIUM
        return ComplexityTier.HIGH

    @staticmethod
    def _unique_verbs(ast: AstNode) -> set[str]:
        verbs: set[str] = set()
        for node in ast.walk():
            if isinstance(node, StatementNode):
                verb = node.attributes.get("verb")
                if verb:
                    verbs.add(verb)
        return verbs

    @staticmethod
    def _count_cross_refs(ast: AstNode) -> int:
        count = 0
        for node in ast.walk():
            if isinstance(node, StatementNode) and node.attributes.get("verb") == "PERFORM":
                count += 1
            if isinstance(node, StatementNode) and node.attributes.get("verb") == "CALL":
                count += 1
        return count

    @staticmethod
    def _has_high_tier_construct(ast: AstNode) -> int:
        for node in ast.walk():
            if isinstance(node, StatementNode):
                verb = node.attributes.get("verb", "")
                if verb in HIGH_TIER_VERBS:
                    return 1
                operands = node.attributes.get("operands", []) or []
                for op in operands:
                    if str(op).upper() in HIGH_TIER_KEYWORDS:
                        return 1
        return 0
