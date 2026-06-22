
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from src.utils.logging import get_logger

log = get_logger(__name__)


class NliLabel(str, Enum):
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    NEI = "NEI"


@dataclass
class SemanticCheckResult:
    label: NliLabel
    confidence: float
    cobol_comment: str
    python_docstring: str
    source: str = "nli"                      


_HF_LABEL_MAP = {
    "ENTAILMENT": NliLabel.SUPPORTED,
    "ENTAIL": NliLabel.SUPPORTED,
    "SUPPORTED": NliLabel.SUPPORTED,
    "SUPPORTS": NliLabel.SUPPORTED,
    "NEUTRAL": NliLabel.NEI,
    "NOT_ENOUGH_INFO": NliLabel.NEI,
    "NEI": NliLabel.NEI,
    "CONTRADICTION": NliLabel.REFUTED,
    "REFUTED": NliLabel.REFUTED,
    "REFUTES": NliLabel.REFUTED,
}


class SemanticValidator:

    def __init__(
        self,
        model_name: str = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
        checkpoint_dir: str | Path | None = None,
        confidence_threshold: float = 0.70,
        fallback_to_lexical: bool = True,
    ) -> None:
        self.model_name = model_name
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else None
        self.confidence_threshold = confidence_threshold
        self.fallback_to_lexical = fallback_to_lexical
        self._pipeline = None
        self._fallback = LexicalFallbackValidator()

    @property
    def is_loaded(self) -> bool:
        return self._pipeline is not None

    def load(self) -> None:
        if self.is_loaded:
            return
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise ImportError("transformers is required for the NLI validator") from exc
        source = str(self.checkpoint_dir) if self.checkpoint_dir and self.checkpoint_dir.exists() else self.model_name
        log.info(f"Loading NLI classifier from {source}")
        self._pipeline = pipeline("text-classification", model=source, top_k=None)

    def check(self, cobol_comment: str, python_docstring: str) -> SemanticCheckResult:
        comment = (cobol_comment or "").strip()
        docstring = (python_docstring or "").strip()
        if not comment or not docstring:
            return SemanticCheckResult(
                label=NliLabel.NEI,
                confidence=0.0,
                cobol_comment=comment,
                python_docstring=docstring,
                source="empty_input",
            )

        if not self.is_loaded:
            try:
                self.load()
            except Exception as exc:                
                if not self.fallback_to_lexical:
                    raise
                log.warning(f"NLI load failed ({exc}); using lexical fallback")
                return self._fallback.check(comment, docstring)

        try:
            premise_hypothesis = f"{comment} [SEP] {docstring}"
            scores = self._pipeline(premise_hypothesis)
                                                                    
            if isinstance(scores, list) and scores and isinstance(scores[0], list):
                scores = scores[0]
            best = max(scores, key=lambda s: s["score"])
            label = _HF_LABEL_MAP.get(best["label"].upper(), NliLabel.NEI)
            return SemanticCheckResult(
                label=label,
                confidence=float(best["score"]),
                cobol_comment=comment,
                python_docstring=docstring,
                source="nli",
            )
        except Exception as exc:                
            if not self.fallback_to_lexical:
                raise
            log.warning(f"NLI inference failed ({exc}); using lexical fallback")
            return self._fallback.check(comment, docstring)


class LexicalFallbackValidator:

    _STOPWORDS = frozenset(
        {
            "a", "an", "and", "the", "of", "to", "for", "by", "is", "are",
            "was", "were", "be", "been", "this", "that", "with", "from",
            "in", "on", "as", "or", "it", "its", "we", "you", "they",
        }
    )
    _SUPPORTED_THRESHOLD = 0.55
    _REFUTED_THRESHOLD = 0.10

    def check(self, comment: str, docstring: str) -> SemanticCheckResult:
        a = self._tokens(comment)
        b = self._tokens(docstring)
        if not a or not b:
            return SemanticCheckResult(
                label=NliLabel.NEI,
                confidence=0.0,
                cobol_comment=comment,
                python_docstring=docstring,
                source="lexical",
            )
        intersection = a & b
        union = a | b
        jaccard = len(intersection) / len(union)
                                                                                     
        confidence = 1.0 / (1.0 + math.exp(-8 * (jaccard - 0.3)))

        if jaccard >= self._SUPPORTED_THRESHOLD:
            label = NliLabel.SUPPORTED
        elif jaccard <= self._REFUTED_THRESHOLD:
            label = NliLabel.REFUTED
            confidence = 1.0 - confidence
        else:
            label = NliLabel.NEI

        return SemanticCheckResult(
            label=label,
            confidence=round(confidence, 4),
            cobol_comment=comment,
            python_docstring=docstring,
            source="lexical",
        )

    def _tokens(self, text: str) -> set[str]:
        words = re.findall(r"[A-Za-z0-9]+", text.lower())
        return {w for w in words if w not in self._STOPWORDS and len(w) > 1}
