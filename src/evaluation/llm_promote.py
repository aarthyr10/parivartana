
from __future__ import annotations

from dataclasses import dataclass

from src.pipeline.stage3_llm.providers import LLMProvider


PROMOTE_SYSTEM = """You decide whether a Python file is a faithful
translation of a COBOL program.

Reply with a single word — YES or NO — followed by an optional very
short reason on the same line.

Say YES when the Python:
  - covers the major operations of the COBOL (data init, paragraphs,
    arithmetic, conditional logic, DISPLAY/output),
  - uses idiomatic Python rather than literal transliteration,
  - does not crash at import time (no obvious NameError, SyntaxError,
    or broken references),
  - matches the COBOL's *intent* even if internal naming or structure
    differs slightly.

Say NO when there is a meaningful divergence — paragraphs missing,
arithmetic transformed wrongly, output verbs dropped, identifiers
absent.

Do not nitpick formatting, comments, or idiomatic style differences."""


PROMOTE_USER_TEMPLATE = """COBOL program:
```cobol
{cobol}
```

Candidate Python translation:
```python
{python}
```

YES or NO?"""


@dataclass
class PromoteResult:
    promoted: bool                                    
    answered: bool                                                   
    raw_text: str                                            
    reason: str                                               
    provider: str = ""
    error: str = ""


def _parse_reply(text: str) -> tuple[bool | None, str]:
    if not text:
        return None, ""
    stripped = text.strip().lstrip("`").lstrip()
    head = stripped[:6].upper()
    answer: bool | None
    if head.startswith("YES"):
        answer = True
        reason = stripped[3:].lstrip(" ,.:;-")
    elif head.startswith("NO"):
        answer = False
        reason = stripped[2:].lstrip(" ,.:;-")
    else:
        answer = None
        reason = stripped[:160]
    return answer, reason[:200]


def llm_promote(
    cobol_source: str,
    python_source: str,
    provider: LLMProvider,
) -> PromoteResult:
    if not provider.is_available():
        return PromoteResult(
            promoted=False,
            answered=False,
            raw_text="",
            reason="",
            provider=provider.name,
            error=f"{provider.name}: no API key",
        )
    if not cobol_source or not python_source:
        return PromoteResult(
            promoted=False,
            answered=False,
            raw_text="",
            reason="",
            provider=provider.name,
            error="empty input",
        )

    user = PROMOTE_USER_TEMPLATE.format(
                                                                  
                                                                 
        cobol=cobol_source[:8000],
        python=python_source[:8000],
    )
    try:
        response = provider.complete(PROMOTE_SYSTEM, user)
    except Exception as exc:                
        return PromoteResult(
            promoted=False,
            answered=False,
            raw_text="",
            reason="",
            provider=provider.name,
            error=f"{provider.name}: {exc}"[:240],
        )

    answer, reason = _parse_reply(response.text or "")
    return PromoteResult(
        promoted=(answer is True),
        answered=(answer is not None),
        raw_text=(response.text or "")[:240],
        reason=reason,
        provider=provider.name,
    )
