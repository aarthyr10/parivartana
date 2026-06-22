
from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.pipeline.stage1_parser.ast_nodes import AstNode
from src.utils.io import write_json
from src.utils.paths import RUNS_DIR, ensure_dir


_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe(name: str) -> str:
    return _SAFE_ID_RE.sub("_", (name or "unknown")).strip("_") or "unknown"


@dataclass
class StageTrace:
    program_id: str
    record_id: str = ""

    cobol_source: str = ""

    stage1_ok: bool = False
    stage1_program_id: str = ""
    stage1_division_count: int = 0
    stage1_paragraph_count: int = 0
    stage1_token_count: int = 0
    stage1_ast: dict[str, Any] | None = None
    stage1_warnings: list[str] = field(default_factory=list)
    stage1_errors: list[str] = field(default_factory=list)
                                                                   
                                                  
    stage1_cobc_status: str = ""
    stage1_cobc_stderr: str = ""

    complexity_tier: str = ""
    complexity_score: float = 0.0
    ast_depth: int = 0
    unique_verbs: int = 0
    cross_refs: int = 0

    stage2_source: str = ""
    stage2_rule_based_code: str = ""
    stage2_neural_code: str = ""
    stage2_final_code: str = ""
    stage2_warnings: list[str] = field(default_factory=list)
    stage2_rescue_status: str = ""
    stage2_todo_count: int = 0

    stage3_ran: bool = False
    stage3_refined_code: str = ""
    stage3_rename_map: dict[str, str] = field(default_factory=dict)
    stage3_docstrings_added: int = 0
    stage3_semantic_label: str = ""
    stage3_provider: str = ""
    stage3_error: str = ""

    verdict: str = ""
    verdict_summary: str = ""
    verdict_checks: list[dict] = field(default_factory=list)

    timestamp: float = field(default_factory=time.time)


def ast_to_dict(node: AstNode | None) -> dict[str, Any] | None:
    if node is None:
        return None
    return node.to_dict()


def write_trace(trace: StageTrace, out_dir: Path | None = None) -> Path:
    target_dir = ensure_dir(out_dir or RUNS_DIR)
    stamp = int(trace.timestamp)
    fname = f"{_safe(trace.program_id)}__{_safe(trace.record_id)}__{stamp}.json"
    path = target_dir / fname
    write_json(path, asdict(trace))
    return path


def todo_count(python_code: str) -> int:
    if not python_code:
        return 0
    return len(re.findall(r"# TODO: unsupported COBOL verb", python_code))


def build_trace_from_row(row: dict[str, Any]) -> StageTrace:
    trace = StageTrace(
        program_id=row.get("program_id") or "(unnamed)",
        record_id=str(row.get("id") or ""),
        cobol_source=row.get("cobol_source", ""),
        stage1_ok=bool(row.get("ok")),
        stage1_warnings=list(row.get("stage1_warnings", []) or []),
        stage1_errors=list(row.get("errors", []) or []),
        complexity_tier=row.get("tier") or "",
        complexity_score=float(row.get("complexity") or 0.0),
        ast_depth=int(row.get("ast_depth") or 0),
        unique_verbs=int(row.get("verbs") or 0),
        cross_refs=int(row.get("cross_refs") or 0),
        stage2_source=row.get("stage2_source") or "",
        stage2_rule_based_code=row.get("rule_based_python_original")
        or row.get("rule_based_python", ""),
        stage2_neural_code=row.get("neural_python", ""),
        stage2_final_code=row.get("rule_based_python", ""),
        stage2_warnings=list(row.get("stage2_warnings", []) or []),
        stage2_rescue_status=row.get("rescue_status") or "",
        stage2_todo_count=todo_count(row.get("rule_based_python", "")),
        stage3_ran=bool(row.get("refined_python")),
        stage3_refined_code=row.get("refined_python", ""),
        stage3_rename_map=dict(row.get("rename_map", {}) or {}),
        stage3_docstrings_added=int(row.get("docstrings_added") or 0),
        stage3_semantic_label=row.get("semantic_label") or "",
        stage3_provider=row.get("stage3_provider") or "",
        stage3_error=row.get("stage3_error") or "",
        verdict=row.get("verdict") or "",
        verdict_summary=row.get("verdict_summary") or "",
        verdict_checks=list(row.get("verdict_checks", []) or []),
    )
    if row.get("ast_obj") is not None:
        trace.stage1_ast = ast_to_dict(row["ast_obj"])
    if row.get("stage1_program_id"):
        trace.stage1_program_id = row["stage1_program_id"]
    if row.get("stage1_division_count") is not None:
        trace.stage1_division_count = int(row["stage1_division_count"])
    if row.get("stage1_paragraph_count") is not None:
        trace.stage1_paragraph_count = int(row["stage1_paragraph_count"])
    if row.get("stage1_token_count") is not None:
        trace.stage1_token_count = int(row["stage1_token_count"])
    return trace
