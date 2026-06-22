
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.evaluation.judge import (
    JUDGE_SYSTEM,
    JUDGE_USER_TEMPLATE,
    JudgeScore,
    LlmJudge,
    _extract_json,
    set_cache_path,
)
from src.evaluation.verifier import (
    VERDICT_INCONCLUSIVE,
    _snake as verifier_snake,
    verify,
)
from src.pipeline.stage1_parser.parser import CobolParser
from src.pipeline.stage2_neural.rule_based import _snake as translator_snake
from src.pipeline.stage3_llm.providers import LLMProvider, LLMResponse


@pytest.mark.parametrize(
    "name",
    [
        "PASS",                      
        "CLASS",                     
        "RETURN",                    
        "GLOBAL",                    
        "MAIN-PARA",
        "END-RTN-EXIT",
        "01-LEVEL",                 
        "WS-AMOUNT",
    ],
)
def test_snake_parity_between_verifier_and_translator(name):
    assert verifier_snake(name) == translator_snake(name)


def test_paragraph_pass_keyword_is_found_after_fix():
    cobol = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY "HELLO".
       PASS.
           DISPLAY "PASS".
       STOP RUN.
"""
    ast = CobolParser().parse(cobol).ast
                                                                    
    python = (
        "def main_para() -> None:\n    print('HELLO')\n\n"
        "def pass_() -> None:\n    print('PASS')\n"
    )
    report = verify(
        cobol_source=cobol,
        python_source=python,
        ast=ast,
        run_execution=False,
        run_llm_judge=False,
    )
    para = report.get("paragraph_coverage")
    assert para.passed is True
    assert para.score == 1.0


class _FakeProvider(LLMProvider):

    name = "fake"

    def __init__(self, text: str, truncated: bool, finish_reason: str = "stop") -> None:
        super().__init__(model="fake-model", max_tokens=10)
        self._text = text
        self._truncated = truncated
        self._finish = finish_reason

    def is_available(self) -> bool:
        return True

    def complete(self, system: str, user: str) -> LLMResponse:
        return LLMResponse(
            text=self._text,
            provider=self.name,
            model=self.model,
            finish_reason=self._finish,
            truncated=self._truncated,
        )


def test_refiner_discards_truncated_output():
    from src.pipeline.stage3_llm.refiner import LLMRefiner

                                                                       
    truncated_text = "def main():\n    print('hel"                      
    renamed = "def main() -> None:\n    print('hello world')\n"
    refiner = LLMRefiner(provider=_FakeProvider(truncated_text, truncated=True, finish_reason="length"))
    result = refiner.refine(
        raw_python=renamed,
        cobol_identifiers=[],
        run_semantic_check=False,
        run_docstring_synthesis=False,
    )
    assert result.refined_python == renamed
    assert result.metadata.get("llm_truncated") is True


def test_refiner_keeps_complete_output():
    from src.pipeline.stage3_llm.refiner import LLMRefiner

    complete_text = "def main() -> None:\n    print('refined!')\n"
    renamed = "def main() -> None:\n    print('original')\n"
    refiner = LLMRefiner(provider=_FakeProvider(complete_text, truncated=False, finish_reason="stop"))
    result = refiner.refine(
        raw_python=renamed,
        cobol_identifiers=[],
        run_semantic_check=False,
        run_docstring_synthesis=False,
    )
    assert "refined!" in result.refined_python
    assert not result.metadata.get("llm_truncated")


@pytest.mark.parametrize(
    "wrapped",
    [
        '{"a": 1}',
        '```json\n{"a": 1}\n```',
        '```\n{"a": 1}\n```',
        'Here is the JSON:\n```json\n{"a": 1, "b": 2}\n```',
        'Sure!\n{"a": 1}\nLet me know if you need anything else.',
        'Response: {"a": 1, "b": [2, 3]}',
    ],
)
def test_extract_json_strips_llm_wrapping(wrapped):
    out = _extract_json(wrapped)
    assert json.loads(out)                  


def test_judge_uses_extract_json_via_fake_provider(tmp_path):
                                                                      
                        
    set_cache_path(tmp_path / "cache.json")
    try:
        wrapped = (
            "Here is the JSON:\n```json\n"
            '{"correctness": 0.9, "readability": 0.8, "pep8_compliance": 0.85, '
            '"pythonic_idioms": 0.8, "type_annotations": 0.7, "rationale": "ok"}\n```'
        )
        judge = LlmJudge(provider=_FakeProvider(wrapped, truncated=False))
        score = judge.score("COBOL HERE", "python here")
        assert isinstance(score, JudgeScore)
        assert score.correctness == 0.9
        assert score.weighted > 0.78                                         
    finally:
        set_cache_path(None)


def test_skipped_reason_concatenates_provider_attempts(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    cobol = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY "HELLO".
       STOP RUN.
"""
    ast = CobolParser().parse(cobol).ast
    python = 'def main_para() -> None:\n    print("HELLO")\n'
    report = verify(
        cobol_source=cobol,
        python_source=python,
        ast=ast,
        run_execution=False,
        run_llm_judge=True,
        llm_provider=["openai", "anthropic"],
    )
    judge = report.get("llm_judge")
    assert judge.ran is False
                                                                       
    assert "openai" in judge.skipped_reason
    assert "anthropic" in judge.skipped_reason
    assert "|" in judge.skipped_reason
                                          
    tried = judge.extra.get("providers_tried") or []
    assert len(tried) == 2
                                                                
                                                                     
    assert report.verdict in {"STRUCTURAL_PASS", VERDICT_INCONCLUSIVE}


class _CountingProvider(_FakeProvider):
    def __init__(self, text: str) -> None:
        super().__init__(text, truncated=False)
        self.calls = 0

    def complete(self, system: str, user: str) -> LLMResponse:
        self.calls += 1
        return super().complete(system, user)


def test_judge_cache_avoids_second_api_call(tmp_path):
    set_cache_path(tmp_path / "cache.json")
    try:
        payload = (
            '{"correctness": 0.9, "readability": 0.8, "pep8_compliance": 0.85, '
            '"pythonic_idioms": 0.8, "type_annotations": 0.7, "rationale": "ok"}'
        )
        prov = _CountingProvider(payload)
        judge = LlmJudge(provider=prov)
        s1 = judge.score("COBOL", "python")
        s2 = judge.score("COBOL", "python")                           
        assert prov.calls == 1
        assert s1.weighted == s2.weighted
                                       
        judge.score("COBOL2", "python")
        assert prov.calls == 2
    finally:
        set_cache_path(None)
