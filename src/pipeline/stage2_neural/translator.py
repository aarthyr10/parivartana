
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from src.pipeline.stage1_parser.ast_nodes import AstNode
from src.pipeline.stage1_parser.complexity import ComplexityTier
from src.pipeline.stage2_neural.prompt_builder import SPECIAL_TOKENS, PromptBuilder
from src.pipeline.stage2_neural.rule_based import RuleBasedTranslator
from src.utils.logging import get_logger

log = get_logger(__name__)


_TIER_DECODE_PARAMS: dict[ComplexityTier, dict] = {
    ComplexityTier.SIMPLE: {"num_beams": 4, "max_new_tokens": 256},
    ComplexityTier.MEDIUM: {"num_beams": 6, "max_new_tokens": 384},
    ComplexityTier.HIGH: {"num_beams": 8, "max_new_tokens": 512},
}


@dataclass
class TranslationResult:
    python_code: str
    tier: ComplexityTier
    model_name: str
    inference_time_ms: float = 0.0
    confidence: float | None = None
    metadata: dict = field(default_factory=dict)


class NeuralTranslator:

    def __init__(
        self,
        model_name: str = "Salesforce/codet5p-220m",
        checkpoint_dir: str | Path | None = None,
        device: str = "auto",
        max_input_length: int = 1024,
        max_output_length: int = 512,
        fallback_to_rules: bool = True,
    ) -> None:
        self.model_name = model_name
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else None
        self.device = device
        self.max_input_length = max_input_length
        self.max_output_length = max_output_length
        self.fallback_to_rules = fallback_to_rules

        self._model = None
        self._tokenizer = None
        self._torch = None
        self._prompt_builder = PromptBuilder(max_tokens=max_input_length)
        self._fallback = RuleBasedTranslator()

                                                                        
    @property
    def is_loaded(self) -> bool:
        return self._model is not None and self._tokenizer is not None

    def load(self) -> None:
        if self.is_loaded:
            return
        try:
            import torch              
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise ImportError("transformers + torch are required for Stage 2 inference") from exc
        self._torch = __import__("torch")

        source = str(self.checkpoint_dir) if self.checkpoint_dir and self.checkpoint_dir.exists() else self.model_name
        log.info(f"Loading CodeT5+ model from {source}")
                                                                     
                                                                     
        self._tokenizer = self._load_tokenizer_robust(source)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(source)

                                                                        
        new_tokens = [t for t in SPECIAL_TOKENS if t not in self._tokenizer.get_vocab()]
        if new_tokens:
            self._tokenizer.add_special_tokens({"additional_special_tokens": new_tokens})
            self._model.resize_token_embeddings(len(self._tokenizer))
            log.info(f"Added {len(new_tokens)} structural special tokens")

        device = self._resolve_device()
        self._model.to(device)
        self._model.eval()

    @staticmethod
    def _load_tokenizer_robust(source: str):
        from transformers import AutoTokenizer

        def _is_addedtoken_err(exc: BaseException) -> bool:
            msg = str(exc)
            return (
                "List[Union[str, AddedToken]]" in msg
                or "must be either str or AddedToken" in msg
            )

        try:
            return AutoTokenizer.from_pretrained(source)
        except (TypeError, ValueError) as exc:
            if not _is_addedtoken_err(exc):
                raise
        try:
            return AutoTokenizer.from_pretrained(source, use_fast=False)
        except (TypeError, ValueError) as exc:
            if not _is_addedtoken_err(exc):
                raise

        from pathlib import Path as _Path

        from src.pipeline.stage2_neural._tokenizer_patch import (
            materialise_clean_tokenizer,
            patch_existing_directory,
        )

        if _Path(source).exists():
                                                                         
                                                               
            patch_existing_directory(source)
            return AutoTokenizer.from_pretrained(source)

        patched = materialise_clean_tokenizer(source)
        return AutoTokenizer.from_pretrained(str(patched))

    def _resolve_device(self) -> str:
        if self.device != "auto":
            return self.device
        torch = self._torch
        if torch is not None and torch.cuda.is_available():
            return "cuda"
        if torch is not None and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

                                                                        
    def translate(self, ast: AstNode, tier: ComplexityTier) -> TranslationResult:
        prompt = self._prompt_builder.build(ast, tier)
        start = time.perf_counter()

        if not self.is_loaded:
            try:
                self.load()
            except Exception as exc:                                          
                if not self.fallback_to_rules:
                    raise
                log.warning(f"Model load failed ({exc}); using rule-based fallback")
                return self._fallback_result(ast, tier, start, reason=str(exc))

        try:
            decode_params = _TIER_DECODE_PARAMS.get(tier, _TIER_DECODE_PARAMS[ComplexityTier.MEDIUM])
            inputs = self._tokenizer(
                prompt.text,
                return_tensors="pt",
                truncation=True,
                max_length=self.max_input_length,
            ).to(self._model.device)

            with self._torch.no_grad():
                outputs = self._model.generate(
                    **inputs,
                    num_beams=decode_params["num_beams"],
                    max_new_tokens=decode_params["max_new_tokens"],
                    early_stopping=True,
                    output_scores=True,
                    return_dict_in_generate=True,
                )

            python_code = self._tokenizer.decode(outputs.sequences[0], skip_special_tokens=True)
            elapsed = (time.perf_counter() - start) * 1000.0
            confidence = self._sequence_confidence(outputs)
            return TranslationResult(
                python_code=python_code,
                tier=tier,
                model_name=self.model_name,
                inference_time_ms=round(elapsed, 2),
                confidence=confidence,
                metadata={
                    "prompt_tokens": prompt.token_count,
                    "tier_tag": prompt.tier_tag,
                    "num_beams": decode_params["num_beams"],
                    "fallback": False,
                },
            )
        except Exception as exc:                
            if not self.fallback_to_rules:
                raise
            log.warning(f"Generation failed ({exc}); using rule-based fallback")
            return self._fallback_result(ast, tier, start, reason=str(exc))

    def batch_translate(
        self, asts: list[AstNode], tiers: list[ComplexityTier]
    ) -> list[TranslationResult]:
        if len(asts) != len(tiers):
            raise ValueError("asts and tiers must have the same length")
        return [self.translate(ast, tier) for ast, tier in zip(asts, tiers, strict=True)]

                                                                        
    def _sequence_confidence(self, outputs) -> float | None:
        scores = getattr(outputs, "sequences_scores", None)
        if scores is None or len(scores) == 0:
            return None
        try:
            return float(self._torch.exp(scores[0]).item())
        except Exception:                
            return None

    def _fallback_result(
        self, ast: AstNode, tier: ComplexityTier, start: float, reason: str
    ) -> TranslationResult:
        translated = self._fallback.translate(ast)
        elapsed = (time.perf_counter() - start) * 1000.0
        return TranslationResult(
            python_code=translated.code,
            tier=tier,
            model_name="rule-based-fallback",
            inference_time_ms=round(elapsed, 2),
            confidence=None,
            metadata={
                "fallback": True,
                "fallback_reason": reason,
                "warnings": translated.warnings,
                "paragraphs": translated.paragraphs,
            },
        )
