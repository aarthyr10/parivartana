from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CodeBleuComponents:
    ngram_match: float
    weighted_ngram_match: float
    syntax_match: float
    dataflow_match: float
    final_score: float


class CodeBleuScorer:
    def __init__(
        self,
        weights: tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.25),
        lang: str = "python",
    ) -> None:
        self.weights = weights
        self.lang = lang

    def score(self, reference: str, hypothesis: str) -> CodeBleuComponents:
        try:
            from codebleu import calc_codebleu
        except ImportError as exc:
            raise ImportError(
                "Install the codebleu package to compute CodeBLEU "
                "(pip install codebleu) or call score_bleu_only() instead."
            ) from exc

        result = calc_codebleu([reference], [hypothesis], lang=self.lang, weights=self.weights)
        return CodeBleuComponents(
            ngram_match=float(result["ngram_match_score"]),
            weighted_ngram_match=float(result["weighted_ngram_match_score"]),
            syntax_match=float(result["syntax_match_score"]),
            dataflow_match=float(result["dataflow_match_score"]),
            final_score=float(result["codebleu"]),
        )

    def score_bleu_only(self, reference: str, hypothesis: str) -> float:
        from sacrebleu import corpus_bleu

        bleu = corpus_bleu([hypothesis], [[reference]])
        return float(bleu.score) / 100.0
