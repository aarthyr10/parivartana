from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.utils.io import read_jsonl
from src.utils.logging import get_logger

log = get_logger(__name__)


COBOL_SCOPE_PREFIXES = {
    "WS": "working_storage",
    "FD": "file",
    "LS": "linkage",
    "LK": "linkage",
    "CONST": "constant",
}

TYPE_SUFFIXES = {
    "AMT": "amount",
    "CNT": "count",
    "NUM": "number",
    "DT": "date",
    "TM": "time",
    "ID": "id",
    "NM": "name",
    "DESC": "description",
    "FLG": "flag",
    "PCT": "percent",
}


@dataclass
class IdentifierMapping:
    cobol_name: str
    python_name: str
    domain: str | None = None
    confidence: str = "MEDIUM"
    source: str = "rule"


class IdentifierRenamer:
    def __init__(self, dictionary_path: str | Path | None = None) -> None:
        self.dictionary: dict[str, IdentifierMapping] = {}
        if dictionary_path:
            self.load_dictionary(dictionary_path)

    def load_dictionary(self, path: str | Path) -> int:
        path = Path(path)
        if not path.exists():
            log.warning(f"Identifier dictionary not found at {path}")
            return 0
        records = read_jsonl(path)
        for rec in records:
            mapping = IdentifierMapping(
                cobol_name=rec["cobol_name"].upper(),
                python_name=rec["python_name"],
                domain=rec.get("domain"),
                confidence=rec.get("confidence", "MEDIUM"),
                source="dictionary",
            )
            self.dictionary[mapping.cobol_name] = mapping
        log.info(f"Loaded {len(self.dictionary)} identifier mappings")
        return len(self.dictionary)

    def rename(self, cobol_identifier: str) -> IdentifierMapping:
        key = cobol_identifier.upper()
        if key in self.dictionary:
            return self.dictionary[key]
        return self._rule_based_rename(cobol_identifier)

    def _rule_based_rename(self, cobol_identifier: str) -> IdentifierMapping:
        parts = re.split(r"[-_]", cobol_identifier.upper())
        parts = [p for p in parts if p]

        scope_prefix: str | None = None
        if parts and parts[0] in COBOL_SCOPE_PREFIXES:
            parts = parts[1:]

        type_suffix: str | None = None
        if parts and parts[-1] in TYPE_SUFFIXES:
            type_suffix = TYPE_SUFFIXES[parts[-1]]
            parts = parts[:-1]

        body = "_".join(p.lower() for p in parts) or "value"
        if type_suffix:
            body = f"{body}_{type_suffix}"

        return IdentifierMapping(
            cobol_name=cobol_identifier.upper(),
            python_name=body,
            confidence="LOW",
            source="rule",
        )

    def bulk_rename(
        self,
        code: str,
        identifiers: list[str],
    ) -> tuple[str, int, list[IdentifierMapping]]:
        applied: list[IdentifierMapping] = []
        count = 0
        for ident in sorted({i for i in identifiers if i}, key=len, reverse=True):
            mapping = self.rename(ident)
            target = mapping.python_name
            if not target:
                continue
                                                                           
                                                                           
            variants = {ident, ident.replace("-", "_")}
            variants = {v for v in variants if v and v != target}
            applied_here = False
            for variant in sorted(variants, key=len, reverse=True):
                pattern = re.compile(rf"\b{re.escape(variant)}\b")
                new_code, n = pattern.subn(target, code)
                if n:
                    code = new_code
                    count += n
                    applied_here = True
            if applied_here:
                applied.append(mapping)
        return code, count, applied
