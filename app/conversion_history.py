
from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.utils.paths import OUTPUTS_DIR, ensure_dir

CONVERSIONS_DIR = OUTPUTS_DIR / "conversions"


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", text or "program").strip("_")
    return s.lower()[:48] or "program"


@dataclass
class ConversionRecord:

    record_id: str
    created_at: float                
    program_id: str
    tier: str
    complexity_score: float
    cobol_source: str
    rule_based_python: str
    neural_python: str | None
    refined_python: str
    semantic_label: str
    semantic_confidence: float | None
    semantic_source: str | None
    rename_count: int
    pipeline_steps: list[str]
    stage_timings_ms: dict[str, float]
    provider: str
    fallback_used: bool
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def filename(self) -> str:
        return f"{int(self.created_at)}_{_slug(self.program_id)}_{self.record_id[:8]}.json"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "ConversionRecord":
                                                         
        return cls(
            record_id=raw.get("record_id") or uuid.uuid4().hex,
            created_at=float(raw.get("created_at") or time.time()),
            program_id=raw.get("program_id") or "(unnamed)",
            tier=raw.get("tier") or "simple",
            complexity_score=float(raw.get("complexity_score") or 0.0),
            cobol_source=raw.get("cobol_source") or "",
            rule_based_python=raw.get("rule_based_python") or "",
            neural_python=raw.get("neural_python"),
            refined_python=raw.get("refined_python") or "",
            semantic_label=raw.get("semantic_label") or "not_run",
            semantic_confidence=raw.get("semantic_confidence"),
            semantic_source=raw.get("semantic_source"),
            rename_count=int(raw.get("rename_count") or 0),
            pipeline_steps=list(raw.get("pipeline_steps") or []),
            stage_timings_ms=dict(raw.get("stage_timings_ms") or {}),
            provider=raw.get("provider") or "",
            fallback_used=bool(raw.get("fallback_used", False)),
            notes=raw.get("notes") or "",
            extra=dict(raw.get("extra") or {}),
        )


def save_conversion(record: ConversionRecord, directory: Path | str | None = None) -> Path:
    target_dir = Path(directory) if directory else CONVERSIONS_DIR
    ensure_dir(target_dir)
    path = target_dir / record.filename
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(record.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return path


def list_conversions(directory: Path | str | None = None) -> list[ConversionRecord]:
    target_dir = Path(directory) if directory else CONVERSIONS_DIR
    if not target_dir.exists():
        return []
    out: list[ConversionRecord] = []
    for p in target_dir.glob("*.json"):
        try:
            out.append(ConversionRecord.from_dict(json.loads(p.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, KeyError, ValueError):
                                                          
            continue
    out.sort(key=lambda r: r.created_at, reverse=True)
    return out


def load_conversion(record_id: str, directory: Path | str | None = None) -> ConversionRecord | None:
    target_dir = Path(directory) if directory else CONVERSIONS_DIR
    if not target_dir.exists():
        return None
    for p in target_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data.get("record_id") == record_id:
            return ConversionRecord.from_dict(data)
    return None


def delete_conversion(record_id: str, directory: Path | str | None = None) -> bool:
    target_dir = Path(directory) if directory else CONVERSIONS_DIR
    if not target_dir.exists():
        return False
    for p in target_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data.get("record_id") == record_id:
            p.unlink()
            return True
    return False


def clear_all(directory: Path | str | None = None) -> int:
    target_dir = Path(directory) if directory else CONVERSIONS_DIR
    if not target_dir.exists():
        return 0
    count = 0
    for p in target_dir.glob("*.json"):
        try:
            p.unlink()
            count += 1
        except OSError:
            continue
                                                                      
    for p in target_dir.glob("*.tmp"):
        try:
            p.unlink()
        except OSError:
            continue
    return count


def new_record_id() -> str:
    return uuid.uuid4().hex
