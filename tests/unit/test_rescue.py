from __future__ import annotations

import ast

from src.pipeline.stage3_llm.providers import LLMProvider, LLMResponse
from src.pipeline.stage3_llm.rescue import (
    RescueResult,
    rescue_translation,
    strip_comments,
)


class _FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, replies: list[str], available: bool = True) -> None:
        super().__init__(model="fake-model")
        self._replies = replies
        self._available = available
        self.calls: list[tuple[str, str]] = []

    def is_available(self) -> bool:
        return self._available

    def complete(self, system: str, user: str) -> LLMResponse:
        self.calls.append((system, user))
        text = self._replies.pop(0) if self._replies else ""
        return LLMResponse(text=text, provider=self.name, model=self.model)


COBOL = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HI.
       PROCEDURE DIVISION.
       MAIN.
           DISPLAY "HI".
           STOP RUN.
"""

BROKEN_PY = "def main(:\n    pass\n"                         


def test_rescue_returns_valid_python_in_one_round():
    good_reply = 'def main():\n    print("HI")\n\nif __name__ == "__main__":\n    main()\n'
    provider = _FakeProvider([good_reply])
    result = rescue_translation(COBOL, BROKEN_PY, provider)
    assert result.valid is True
    assert result.rounds == 1
    ast.parse(result.python_source)
    assert "print" in result.python_source


def test_rescue_retries_on_first_failure():
    bad_reply = "def main(:\n    pass"                
    good_reply = 'def main():\n    print("HI")\n'
    provider = _FakeProvider([bad_reply, good_reply])
    result = rescue_translation(COBOL, BROKEN_PY, provider, max_rounds=2)
    assert result.valid is True
    assert result.rounds == 2
    ast.parse(result.python_source)


def test_rescue_gives_up_after_max_rounds():
    provider = _FakeProvider(["def x(:\n  pass", "still ( broken"], available=True)
    result = rescue_translation(COBOL, BROKEN_PY, provider, max_rounds=2)
    assert result.valid is False
    assert result.rounds == 2
                                                                            
    assert result.python_source == BROKEN_PY
    assert "could not produce valid Python" in (result.error or "")


def test_rescue_skips_when_provider_unavailable():
    provider = _FakeProvider([], available=False)
    result = rescue_translation(COBOL, BROKEN_PY, provider)
    assert result.valid is False
    assert result.rounds == 0
    assert "provider unavailable" in (result.error or "")


def test_strip_comments_drops_hash_lines():
    src = "# top\nx = 1  # inline\nprint(x)\n# bottom\n"
    out = strip_comments(src)
    assert "# top" not in out
    assert "# inline" not in out
    assert "# bottom" not in out
    assert "x = 1" in out
    assert "print(x)" in out


def test_strip_comments_preserves_hash_inside_strings():
    src = 's = "url#fragment"\n# real comment\n'
    out = strip_comments(src)
    assert "url#fragment" in out
    assert "# real" not in out


def test_strip_comments_handles_code_fence_leak():
                                                                 
                              
    src = "def f():\n    return 1\n"
    assert strip_comments(src).strip() == "def f():\n    return 1"


def test_rescue_strips_fenced_response():
                                               
    fenced = '```python\ndef main():\n    print("HI")\n```'
    provider = _FakeProvider([fenced])
    result = rescue_translation(COBOL, BROKEN_PY, provider)
    assert result.valid is True
    assert "```" not in result.python_source
    ast.parse(result.python_source)


def test_rescue_strips_inline_comments_from_response():
                                                                        
    reply_with_comments = (
        "# module doc\n"
        'def main():  # entry point\n'
        '    print("HI")  # output\n'
    )
    provider = _FakeProvider([reply_with_comments])
    result = rescue_translation(COBOL, BROKEN_PY, provider)
    assert result.valid is True
    assert "#" not in result.python_source.replace("__main__", "")                                             
    ast.parse(result.python_source)
