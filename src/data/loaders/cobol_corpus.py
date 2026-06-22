from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from src.data.loaders.base import BaseLoader

COBOL_EXTENSIONS = {".cob", ".cbl", ".cobol", ".cpy", ".CBL", ".COB"}


def _iter_cobol_files(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {e.lower() for e in COBOL_EXTENSIONS}:
            yield path


def _read_with_fallback(path: Path) -> str:
    for enc in ("utf-8", "cp037", "cp500", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_bytes().decode("utf-8", errors="replace")


def _is_complete_cobol_program(source: str) -> bool:
    src_upper = source.upper()
    has_id_div = "IDENTIFICATION DIVISION" in src_upper or "ID DIVISION" in src_upper
    has_program_id = "PROGRAM-ID" in src_upper
    return has_id_div and has_program_id


class NistCobolLoader(BaseLoader):
    dataset_key = "nist_cobol"

    def iter_records(self) -> Iterator[dict[str, Any]]:
        for path in _iter_cobol_files(self.root):
            source = _read_with_fallback(path)
            yield {
                "id": path.stem,
                "relative_path": str(path.relative_to(self.root)),
                "source": source,
                "is_complete_program": _is_complete_cobol_program(source),
                "expected_stdout_path": str(path.with_suffix(".expected"))
                if path.with_suffix(".expected").exists()
                else None,
            }


class IbmOpenCobolLoader(BaseLoader):
    dataset_key = "ibm_open_cobol"

    def iter_records(self) -> Iterator[dict[str, Any]]:
        for path in _iter_cobol_files(self.root):
            domain = path.parent.name
            yield {
                "id": path.stem,
                "relative_path": str(path.relative_to(self.root)),
                "domain": domain,
                "source": _read_with_fallback(path),
            }


class StackV2CobolLoader(BaseLoader):
    dataset_key = "stack_v2_cobol"

    def iter_records(self) -> Iterator[dict[str, Any]]:
        for path in _iter_cobol_files(self.root):
            yield {
                "id": path.stem,
                "relative_path": str(path.relative_to(self.root)),
                "source": _read_with_fallback(path),
            }


class GfgMultilingualLoader(BaseLoader):
    dataset_key = "gfg_multilingual"

    def iter_records(self) -> Iterator[dict[str, Any]]:
        for path in _iter_cobol_files(self.root):
            algorithm = path.parent.name
            yield {
                "id": path.stem,
                "algorithm": algorithm,
                "relative_path": str(path.relative_to(self.root)),
                "source": _read_with_fallback(path),
            }
