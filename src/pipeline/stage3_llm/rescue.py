
from __future__ import annotations

import ast as pyast
import re
from dataclasses import dataclass

from src.pipeline.stage3_llm.providers import LLMProvider
from src.utils.logging import get_logger

log = get_logger(__name__)


RESCUE_SYSTEM_PROMPT = """You are repairing a Python translation of a COBOL program that does not parse.
Your task: analyse what the COBOL program does, then reimplement that exact behaviour in clean Python.

OUTPUT FORMAT — non-negotiable:
1. Output ONLY Python source code. No prose, no markdown fences, no leading explanation.
2. The output MUST parse with ast.parse() — no SyntaxErrors.
3. ABSOLUTELY NO `#` COMMENTS anywhere. Strip every existing comment from the input.
4. NO docstrings. NO triple-quoted strings used as comments.
5. Preserve the original COBOL behaviour: same MOVE/COMPUTE/IF/PERFORM/DISPLAY semantics.
6. Use a top-level `state: dict` to hold WORKING-STORAGE items, matching the broken input.
7. Define one Python function per COBOL paragraph; the entry paragraph is called from `if __name__ == "__main__":`.

If a line in the input starts with `#`, DELETE it — do not translate it, do not keep it.

Return the full corrected Python module."""

RESCUE_USER_TEMPLATE = """COBOL source:
```cobol
{cobol}
```

Broken Python translation (what to repair):
```python
{python}
```
{error_hint}

Reimplement the COBOL behaviour cleanly. Output Python source only — zero `#` comments, zero prose, zero fences."""


@dataclass
class RescueResult:
    python_source: str
    valid: bool
    rounds: int          
    error: str | None = None
    original_broken: str = ""


def _strip_fences(text: str) -> str:
    t = text.strip()
    if not t.startswith("```"):
        return t
    lines = t.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


from src.pipeline.stage3_llm.comment_stripper import strip_comments             


def rescue_translation(
    cobol_source: str,
    broken_python: str,
    provider: LLMProvider,
    max_rounds: int = 2,
) -> RescueResult:
    if not provider.is_available():
        return RescueResult(
            python_source=broken_python,
            valid=False,
            rounds=0,
            error="provider unavailable",
            original_broken=broken_python,
        )

    error_hint = ""
    current = broken_python
    last_error: str | None = None

    for attempt in range(1, max_rounds + 1):
        user = RESCUE_USER_TEMPLATE.format(
            cobol=cobol_source.strip(),
            python=current.strip(),
            error_hint=error_hint,
        )
        try:
            response = provider.complete(RESCUE_SYSTEM_PROMPT, user)
        except Exception as exc:                
            return RescueResult(
                python_source=broken_python,
                valid=False,
                rounds=attempt,
                error=f"LLM call failed: {exc}",
                original_broken=broken_python,
            )

        candidate = strip_comments(_strip_fences(response.text))
        try:
            pyast.parse(candidate)
            return RescueResult(
                python_source=candidate,
                valid=True,
                rounds=attempt,
                error=None,
                original_broken=broken_python,
            )
        except SyntaxError as exc:
            last_error = f"line {exc.lineno}: {exc.msg}"
            error_hint = (
                f"\n\nPrevious attempt still had a SyntaxError ({last_error}). "
                "Fix it and return clean parseable Python."
            )
            current = candidate                                         
            log.warning(f"rescue attempt {attempt} failed: {last_error}")

    return RescueResult(
        python_source=broken_python,
        valid=False,
        rounds=max_rounds,
        error=f"could not produce valid Python in {max_rounds} round(s); last error: {last_error}",
        original_broken=broken_python,
    )
