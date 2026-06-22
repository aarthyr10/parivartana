from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from src.pipeline.stage3_llm.providers import LLMProvider, get_provider


_CACHE_LOCK = threading.Lock()
_CACHE_PATH_OVERRIDE: Path | None = None


def _default_cache_path() -> Path:
    from src.utils.paths import ARTIFACTS_DIR                             

    return ARTIFACTS_DIR / "cache" / "judge_cache.json"


def set_cache_path(path: Path | None) -> None:
    global _CACHE_PATH_OVERRIDE
    _CACHE_PATH_OVERRIDE = path


def _cache_path() -> Path:
    return _CACHE_PATH_OVERRIDE or _default_cache_path()


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def _cache_key(provider: str, model: str, cobol: str, python: str) -> str:
    return f"{provider}|{model}|{_hash(cobol)}|{_hash(python)}"


def _load_cache() -> dict:
    path = _cache_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(data: dict) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
                                                                          
                                                  
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)


def _extract_json(text: str) -> str:
    if not text:
        return text
    t = text.strip()
                                                  
    fence = re.match(r"^```(?:json|JSON)?\s*\n?(.*?)\n?```\s*$", t, re.DOTALL)
    if fence:
        t = fence.group(1).strip()
                                                      
    if not t.startswith("{"):
        first = t.find("{")
        last = t.rfind("}")
        if first != -1 and last > first:
            t = t[first : last + 1]
    return t

JUDGE_SYSTEM = """You are an impartial reviewer scoring a Python translation of a COBOL program.
Score on five dimensions from 0.0 to 1.0:
- correctness: behavioural fidelity to the COBOL source
- readability: clarity and naming
- pep8_compliance: PEP 8 conformance
- pythonic_idioms: use of Python idioms over literal COBOL transliteration
- type_annotations: completeness of type hints

Return strict JSON with keys: correctness, readability, pep8_compliance, pythonic_idioms, type_annotations, rationale."""

JUDGE_USER_TEMPLATE = """COBOL source:
```cobol
{cobol}
```

Candidate Python translation:
```python
{python}
```

Return only the JSON object."""


@dataclass
class JudgeScore:
    correctness: float
    readability: float
    pep8_compliance: float
    pythonic_idioms: float
    type_annotations: float
    rationale: str
    weighted: float


class LlmJudge:
    def __init__(
        self,
        provider: LLMProvider | str = "openai",
        weights: dict | None = None,
        use_cache: bool = True,
    ) -> None:
        self.provider = get_provider(provider) if isinstance(provider, str) else provider
        self.weights = weights or {
            "correctness": 0.30,
            "readability": 0.20,
            "pep8_compliance": 0.15,
            "pythonic_idioms": 0.20,
            "type_annotations": 0.15,
        }
        self.use_cache = use_cache

    def score(self, cobol: str, python: str) -> JudgeScore:
        cobol = cobol[:6000]
        python = python[:6000]
                                                                              
                                                                          
        cache_key = _cache_key(
            self.provider.name, getattr(self.provider, "model", ""), cobol, python
        )
        if self.use_cache:
            with _CACHE_LOCK:
                cache = _load_cache()
            entry = cache.get(cache_key)
            if entry is not None:
                                                                           
                                                                        
                try:
                    weighted = sum(
                        float(entry[k]) * w
                        for k, w in self.weights.items()
                        if k in entry
                    )
                    return JudgeScore(
                        correctness=float(entry.get("correctness", 0.0)),
                        readability=float(entry.get("readability", 0.0)),
                        pep8_compliance=float(entry.get("pep8_compliance", 0.0)),
                        pythonic_idioms=float(entry.get("pythonic_idioms", 0.0)),
                        type_annotations=float(entry.get("type_annotations", 0.0)),
                        rationale=str(entry.get("rationale", "")),
                        weighted=weighted,
                    )
                except (TypeError, ValueError):
                                                                        
                    pass

        prompt = JUDGE_USER_TEMPLATE.format(cobol=cobol, python=python)
        response = self.provider.complete(JUDGE_SYSTEM, prompt)
        cleaned = _extract_json(response.text)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Judge did not return valid JSON (provider={self.provider.name}, "
                f"finish_reason={getattr(response, 'finish_reason', '')!r}): "
                f"{response.text[:240]}"
            ) from exc

        weighted = sum(float(payload[k]) * w for k, w in self.weights.items() if k in payload)
        result = JudgeScore(
            correctness=float(payload.get("correctness", 0.0)),
            readability=float(payload.get("readability", 0.0)),
            pep8_compliance=float(payload.get("pep8_compliance", 0.0)),
            pythonic_idioms=float(payload.get("pythonic_idioms", 0.0)),
            type_annotations=float(payload.get("type_annotations", 0.0)),
            rationale=str(payload.get("rationale", "")),
            weighted=weighted,
        )
                                                                        
                                                     
        if self.use_cache:
            with _CACHE_LOCK:
                cache = _load_cache()
                cache[cache_key] = {
                    "correctness": result.correctness,
                    "readability": result.readability,
                    "pep8_compliance": result.pep8_compliance,
                    "pythonic_idioms": result.pythonic_idioms,
                    "type_annotations": result.type_annotations,
                    "rationale": result.rationale,
                }
                _save_cache(cache)
        return result
