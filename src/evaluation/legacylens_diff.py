
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class CoverageDiff:
    available: bool
    parser_calls: set[str] = field(default_factory=set)
    legacylens_calls: set[str] = field(default_factory=set)
    parser_performs: set[str] = field(default_factory=set)
    legacylens_performs: set[str] = field(default_factory=set)
    parser_io_files: set[str] = field(default_factory=set)
    legacylens_io_files: set[str] = field(default_factory=set)

    @property
    def missed_calls(self) -> set[str]:
        return self.legacylens_calls - self.parser_calls

    @property
    def missed_performs(self) -> set[str]:
        return self.legacylens_performs - self.parser_performs

    @property
    def missed_io_files(self) -> set[str]:
        return self.legacylens_io_files - self.parser_io_files

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "missed_calls": sorted(self.missed_calls),
            "missed_performs": sorted(self.missed_performs),
            "missed_io_files": sorted(self.missed_io_files),
            "parser_call_count": len(self.parser_calls),
            "legacylens_call_count": len(self.legacylens_calls),
            "parser_perform_count": len(self.parser_performs),
            "legacylens_perform_count": len(self.legacylens_performs),
        }


def _extract_from_legacylens(source: str) -> dict[str, list[str]] | None:
    try:
        from cobol_parser import CobolParser                                  
    except Exception:                
        return None
    try:
        p = CobolParser()
        p.load_from_string(source)
                                                 
                                                                  
        return p.extract_all()
    except Exception as exc:                
        log.warning("legacylens extract failed: %s", exc)
        return None


def _names_from_ast(ast) -> tuple[set[str], set[str], set[str]]:
    from src.pipeline.stage1_parser.ast_nodes import StatementNode                             

    calls: set[str] = set()
    performs: set[str] = set()
    io_files: set[str] = set()
    if ast is None:
        return calls, performs, io_files
    for node in ast.walk():
        if not isinstance(node, StatementNode):
            continue
        verb = node.attributes.get("verb", "")
        operands = node.attributes.get("operands") or []
        if not operands:
            continue
        first = str(operands[0]).strip().strip('"').strip("'")
        if verb == "CALL":
            calls.add(first.upper())
        elif verb == "PERFORM":
            performs.add(first.upper())
        elif verb in {"READ", "WRITE", "OPEN", "CLOSE", "REWRITE", "DELETE", "START"}:
            io_files.add(first.upper())
    return calls, performs, io_files


def coverage_diff(cobol_source: str, ast) -> CoverageDiff:
    parser_calls, parser_performs, parser_io = _names_from_ast(ast)
    legacylens = _extract_from_legacylens(cobol_source)
    if legacylens is None:
        return CoverageDiff(
            available=False,
            parser_calls=parser_calls,
            parser_performs=parser_performs,
            parser_io_files=parser_io,
        )

    def _norm(items: list[Any]) -> set[str]:
        out: set[str] = set()
        for item in items or []:
            if isinstance(item, dict):
                                                                               
                name = item.get("name") or item.get("target") or item.get("file")
            else:
                name = item
            if name:
                out.add(str(name).strip().strip('"').strip("'").upper())
        return out

    return CoverageDiff(
        available=True,
        parser_calls=parser_calls,
        parser_performs=parser_performs,
        parser_io_files=parser_io,
        legacylens_calls=_norm(legacylens.get("calls", [])),
        legacylens_performs=_norm(legacylens.get("performs", [])),
        legacylens_io_files=_norm(legacylens.get("io_files", [])),
    )
