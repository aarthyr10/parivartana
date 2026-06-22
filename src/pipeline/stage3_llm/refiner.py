
from __future__ import annotations

from dataclasses import dataclass, field

from src.pipeline.stage1_parser.complexity import ComplexityTier
import ast as pyast

from src.pipeline.stage3_llm.docstring import (
    DocstringSynthesiser,
    annotate_high_tier,
    insert_docstrings,
)
from src.pipeline.stage3_llm.providers import LLMProvider, get_provider
from src.pipeline.stage3_llm.renamer import IdentifierRenamer
from src.pipeline.stage3_llm.comment_stripper import strip_comments
from src.pipeline.stage3_llm.rescue import rescue_translation
from src.pipeline.stage3_llm.semantic_validator import (
    NliLabel,
    SemanticCheckResult,
    SemanticValidator,
)
from src.utils.logging import get_logger

log = get_logger(__name__)


REFINEMENT_SYSTEM_PROMPT = """You are a senior Python engineer refining machine-translated Python that came from a COBOL program.

OUTPUT FORMAT — strict:
- Output ONLY valid Python source code that ast.parse() accepts.
- No prose. No markdown fences. No leading or trailing explanation.
- ABSOLUTELY NO `#` COMMENTS anywhere in the output. Strip every existing `#` line from the input.
- Docstrings ARE allowed (they are not comments). Use them sparingly for module and function purposes.

PRESERVE — non-negotiable:
- Exact runtime behaviour: same MOVE / COMPUTE / IF / PERFORM / DISPLAY semantics.
- Control flow shape: same function decomposition, same loop and branch structure.
- All state mutations and arithmetic.

IMPROVE — within those constraints:
- Apply PEP 8 (naming, whitespace, line length).
- Replace verbose state['x'] patterns with idiomatic Python where SAFE (locals, dataclasses, comprehensions).
- Add precise type hints on every function signature.
- Use Python built-ins where they preserve semantics (print, open, range, enumerate).
- Remove dead `pass` statements that follow a real statement.

CORRECTNESS — use the COBOL source (provided) as the ground truth:
- If a paragraph body is just `pass` or a `# TODO`/stub, IMPLEMENT it faithfully
  from the corresponding COBOL paragraph. An empty translated paragraph is a
  defect, not behaviour to preserve.
- Ensure the program's main flow actually runs the paragraphs the COBOL would
  execute (e.g. don't leave the entrypoint calling a control paragraph whose
  body is empty) — wire the control flow so the real logic executes.
- Keep DISPLAY output faithful to COBOL (operands concatenate with no inserted
  separator).

Return the full refined Python module as-is, ready to execute."""


def _tier_prompt_suffix(tier: ComplexityTier) -> str:
    if tier == ComplexityTier.HIGH:
        return (
            "\n\nNOTE: source COBOL is HIGH complexity. If you are unsure about a "
            "construct, leave it structurally unchanged rather than guessing. Still "
            "no `#` comments — encode any uncertainty as a docstring on the function."
        )
    if tier == ComplexityTier.MEDIUM:
        return "\n\nNOTE: source COBOL is MEDIUM complexity."
    return ""


@dataclass
class RefinementResult:
    refined_python: str
    raw_python: str
    tier: ComplexityTier = ComplexityTier.SIMPLE
    semantic_check: SemanticCheckResult | None = None
    rename_count: int = 0
    provider: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def semantic_label(self) -> str:
        return self.semantic_check.label.value if self.semantic_check else "not_run"


class LLMRefiner:

    def __init__(
        self,
        provider: LLMProvider | str = "openai",
        model: str | None = None,
        identifier_dict_path: str | None = None,
        validator: SemanticValidator | None = None,
        docstring_synthesiser: DocstringSynthesiser | None = None,
    ) -> None:
        if isinstance(provider, str):
            kwargs = {"model": model} if model else {}
            self.provider = get_provider(provider, **kwargs)
        else:
            self.provider = provider
        self.renamer = IdentifierRenamer(identifier_dict_path)
        self.validator = validator or SemanticValidator()
        self.docstring_synthesiser = docstring_synthesiser or DocstringSynthesiser(self.provider)

                                                                        
    def refine(
        self,
        raw_python: str,
        tier: ComplexityTier = ComplexityTier.SIMPLE,
        cobol_identifiers: list[str] | None = None,
        cobol_comment: str | None = None,
        run_semantic_check: bool = True,
        run_docstring_synthesis: bool = True,
        cobol_source: str | None = None,
    ) -> RefinementResult:
        steps: list[str] = []
        metadata: dict = {}

                                                                         
        renamed = raw_python
        rename_count = 0
        if cobol_identifiers:
            renamed, rename_count, applied = self.renamer.bulk_rename(raw_python, cobol_identifiers)
            metadata["renamed_identifiers"] = [m.cobol_name for m in applied]
            steps.append(f"rename:{rename_count}")

                                                                         
        refined = renamed
        if self.provider.is_available():
            try:
                response = self.provider.complete(
                    REFINEMENT_SYSTEM_PROMPT + _tier_prompt_suffix(tier),
                    renamed,
                )
                candidate = _strip_code_fences(response.text) or renamed
                metadata.update(
                    {
                        "model": response.model,
                        "prompt_tokens": response.prompt_tokens,
                        "completion_tokens": response.completion_tokens,
                        "finish_reason": getattr(response, "finish_reason", ""),
                    }
                )

                if getattr(response, "truncated", False):
                    log.warning(
                        "LLM refinement truncated (finish_reason=%s, completion_tokens=%s); "
                        "discarding partial output and keeping renamed code",
                        response.finish_reason,
                        response.completion_tokens,
                    )
                    metadata["llm_truncated"] = True
                    steps.append("llm_refine:truncated")
                else:
                    refined = candidate
                    steps.append("llm_refine")
            except Exception as exc:                
                log.warning(f"LLM refinement failed: {exc}; keeping renamed code")
                metadata["llm_error"] = str(exc)
                steps.append("llm_refine:skipped")
        else:
            log.info(f"Provider {self.provider.name} unavailable; skipping LLM refinement")
            steps.append("llm_refine:no_provider")

                                                                        
        if run_docstring_synthesis and self.provider.is_available():
            try:
                insertions = self.docstring_synthesiser.synthesise(refined, cobol_comment)
                if insertions:
                    refined = insert_docstrings(refined, insertions)
                    metadata["docstrings_added"] = len(insertions)
                    steps.append(f"docstrings:{len(insertions)}")
            except Exception as exc:                
                log.warning(f"Docstring synthesis failed: {exc}")
                steps.append("docstrings:skipped")

                                                                        
        if cobol_source:
            try:
                pyast.parse(refined)
            except SyntaxError as exc:
                if self.provider.is_available():
                    log.warning(
                        f"refined Python failed ast.parse ({exc.msg}); invoking rescue"
                    )
                    rescue = rescue_translation(
                        cobol_source=cobol_source,
                        broken_python=refined,
                        provider=self.provider,
                    )
                    metadata["rescued"] = rescue.valid
                    metadata["rescue_rounds"] = rescue.rounds
                    if rescue.valid:
                        refined = rescue.python_source
                        steps.append(f"rescue:ok:{rescue.rounds}rd")
                    else:
                        steps.append("rescue:failed")
                        metadata["rescue_error"] = rescue.error
                else:
                    metadata["rescued"] = False
                    metadata["rescue_error"] = "provider unavailable"
                    steps.append("rescue:no_provider")

                                                                        
        refined = annotate_high_tier(refined, tier)
        if tier == ComplexityTier.HIGH:
            steps.append("high_tier_banner")

                                                                        
        semantic = None
        if run_semantic_check and cobol_comment:
            python_doc = _extract_module_or_first_docstring(refined)
            try:
                semantic = self.validator.check(cobol_comment, python_doc)
                steps.append(f"semantic:{semantic.label.value}:{semantic.source}")
                if semantic.label == NliLabel.REFUTED:
                    metadata["semantic_warning"] = (
                        f"semantic validator flagged possible meaning drift "
                        f"(confidence {semantic.confidence:.2f})"
                    )
                    steps.append("semantic_warning_recorded")
            except Exception as exc:                
                log.warning(f"Semantic check failed: {exc}")
                steps.append("semantic:skipped")

        refined = strip_comments(refined)
        steps.append("strip_comments")

        metadata["pipeline_steps"] = steps

        return RefinementResult(
            refined_python=refined,
            raw_python=raw_python,
            tier=tier,
            semantic_check=semantic,
            rename_count=rename_count,
            provider=self.provider.name,
            metadata=metadata,
        )


def _strip_code_fences(text: str) -> str:
    t = text.strip()
    if not t.startswith("```"):
        return t
    lines = t.splitlines()
    if lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_module_or_first_docstring(code: str) -> str:
    for quote in ('"""', "'''"):
        start = code.find(quote)
        if start == -1:
            continue
        end = code.find(quote, start + len(quote))
        if end == -1:
            continue
        return code[start + len(quote) : end].strip()
    return ""
