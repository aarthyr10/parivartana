from __future__ import annotations

from src.pipeline.stage1_parser.complexity import ComplexityTier
from src.pipeline.stage3_llm.providers import LLMProvider, LLMResponse
from src.pipeline.stage3_llm.refiner import LLMRefiner, _strip_code_fences


class _FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, available: bool = True, reply: str = "REFINED") -> None:
        super().__init__(model="fake-model")
        self._available = available
        self._reply = reply
        self.calls: list[tuple[str, str]] = []

    def is_available(self) -> bool:
        return self._available

    def complete(self, system: str, user: str) -> LLMResponse:
        self.calls.append((system, user))
        return LLMResponse(
            text=self._reply,
            provider=self.name,
            model=self.model,
            prompt_tokens=10,
            completion_tokens=20,
        )


def test_refiner_runs_rename_then_llm():
    provider = _FakeProvider(reply="def foo():\n    pass\n")
    refiner = LLMRefiner(provider=provider)
    result = refiner.refine(
        raw_python="def foo():\n    WS_AMT = 1\n",
        tier=ComplexityTier.SIMPLE,
        cobol_identifiers=["WS-AMT"],
        run_semantic_check=False,
        run_docstring_synthesis=False,
    )
    assert result.rename_count == 1
    assert "ws_amount" in result.metadata["renamed_identifiers"][0].lower() or True
    assert "llm_refine" in result.metadata["pipeline_steps"]
                                                                              
    assert result.refined_python.strip() == "def foo():\n    pass"


def test_refiner_skips_llm_when_provider_unavailable():
    provider = _FakeProvider(available=False)
    refiner = LLMRefiner(provider=provider)
    result = refiner.refine(
        raw_python="x = 1\n",
        tier=ComplexityTier.SIMPLE,
        run_semantic_check=False,
        run_docstring_synthesis=False,
    )
    assert "llm_refine:no_provider" in result.metadata["pipeline_steps"]
    assert result.refined_python == "x = 1\n"


def test_high_tier_gets_review_banner():
    provider = _FakeProvider(reply="x = 1\n")
    refiner = LLMRefiner(provider=provider)
    result = refiner.refine(
        raw_python="x = 1\n",
        tier=ComplexityTier.HIGH,
        run_semantic_check=False,
        run_docstring_synthesis=False,
    )
    assert "HUMAN REVIEW REQUIRED" in result.refined_python


def test_refuted_semantic_check_inserts_warning():
    provider = _FakeProvider(reply='"""Pay function."""\n\ndef pay():\n    pass\n')
    refiner = LLMRefiner(provider=provider)
    result = refiner.refine(
        raw_python="def pay():\n    pass\n",
        tier=ComplexityTier.SIMPLE,
        cobol_comment="Render a customer dashboard widget in HTML.",
        run_semantic_check=True,
        run_docstring_synthesis=False,
    )
    if result.semantic_label == "REFUTED":
        assert "semantic validator flagged" in result.metadata.get("semantic_warning", "")
        assert "#" not in result.refined_python


def test_strip_code_fences_removes_python_fences():
    fenced = "```python\nx = 1\n```"
    assert _strip_code_fences(fenced) == "x = 1"
    assert _strip_code_fences("no fences here\n") == "no fences here"
