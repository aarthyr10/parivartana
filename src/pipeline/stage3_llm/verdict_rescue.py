
from __future__ import annotations

import re
from dataclasses import dataclass

from src.pipeline.stage3_llm.providers import LLMProvider


VERDICT_RESCUE_SYSTEM = """You repair a Python translation of a COBOL program.

The translation has structural problems (missing functions, stubbed
function bodies, missing identifiers) or runtime problems. Your job:
produce a corrected Python program that:

  1. Defines a function for every COBOL paragraph (snake_case; the
     translator escapes Python keywords with a trailing underscore,
     e.g. ``def pass_():`` for paragraph ``PASS``).
  2. Has a non-trivial body for every function — at minimum, a real
     statement, not just ``pass``.
  3. References every COBOL data identifier somewhere in the code.
  4. Parses cleanly under ``ast.parse``.
  5. Runs without crashing when executed with ``python3``.

Constraints:

  * Keep the existing ``class _State(dict)`` runtime helper and the
    ``state: _State`` module-level dict.
  * Preserve the file's existing imports and the ``if __name__ ==
    "__main__":`` entrypoint block (you may change *which* paragraph
    is called from there if the current one is wrong, e.g. switch
    from ``declaratives()`` to the program's real main).
  * Do not add new external dependencies (anything beyond Python
    stdlib).
  * Wrap any file I/O / ACCEPT in try/except so the program never
    raises at module level.

Return ONLY the corrected Python source — no preamble, no fences."""


VERDICT_RESCUE_USER_TEMPLATE = """COBOL source:
```cobol
{cobol}
```

Current translated Python (failing checks listed below):
```python
{python}
```

Failing verifier checks:
{check_list}

Return the fixed Python source as a single file."""


@dataclass
class VerdictRescueResult:
    rescued: bool
    new_python: str
    error: str = ""
    rounds: int = 0
    provider_used: str = ""


def _format_checks(failing_checks: list[dict]) -> str:
    lines: list[str] = []
    for c in failing_checks:
        name = c.get("name", "?")
        detail = (c.get("detail") or c.get("skipped_reason") or "").strip()
        if detail:
            lines.append(f"- {name}: {detail[:240]}")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines) or "(none specified)"


def _strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    if not t.startswith("```"):
        return t
    m = re.match(r"^```(?:python|py)?\s*\n?(.*?)\n?```\s*$", t, re.DOTALL)
    if m:
        return m.group(1).strip()
                                                           
    lines = t.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def rescue_verdict(
    cobol_source: str,
    failing_python: str,
    failing_checks: list[dict],
    provider: LLMProvider,
) -> VerdictRescueResult:
    if not provider.is_available():
        return VerdictRescueResult(
            rescued=False, new_python="", error=f"{provider.name}: no API key"
        )
    if not cobol_source or not failing_python:
        return VerdictRescueResult(
            rescued=False, new_python="", error="empty input to rescue"
        )

    user = VERDICT_RESCUE_USER_TEMPLATE.format(
        cobol=cobol_source[:30000],
        python=failing_python[:30000],
        check_list=_format_checks(failing_checks),
    )
    try:
        response = provider.complete(VERDICT_RESCUE_SYSTEM, user)
    except Exception as exc:                
        return VerdictRescueResult(
            rescued=False,
            new_python="",
            error=f"{provider.name}: {exc}"[:240],
            provider_used=provider.name,
        )

    candidate = _strip_code_fences(response.text)
    if not candidate.strip():
        return VerdictRescueResult(
            rescued=False, new_python="", error="empty rescue response",
            provider_used=provider.name,
        )

                                                                    
    import ast as _ast
    try:
        _ast.parse(candidate)
    except SyntaxError as exc:
        return VerdictRescueResult(
            rescued=False,
            new_python="",
            error=f"rescue did not parse: line {exc.lineno}: {exc.msg}",
            rounds=1,
            provider_used=provider.name,
        )

                                                                   
    orig_defs = len(re.findall(r"^def\s+\w+", failing_python, re.MULTILINE))
    new_defs = len(re.findall(r"^def\s+\w+", candidate, re.MULTILINE))
    if orig_defs > 0 and new_defs < orig_defs * 0.5:
        return VerdictRescueResult(
            rescued=False,
            new_python="",
            error=f"rescue dropped too many functions ({orig_defs} -> {new_defs})",
            rounds=1,
            provider_used=provider.name,
        )

    return VerdictRescueResult(
        rescued=True,
        new_python=candidate,
        rounds=1,
        provider_used=provider.name,
    )
