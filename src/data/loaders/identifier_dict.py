from __future__ import annotations

from typing import Any, Iterator

from src.data.loaders.base import BaseLoader
from src.utils.io import read_jsonl


class CobolIdentifierDictLoader(BaseLoader):
    dataset_key = "cobol_identifier_dict"

    def iter_records(self) -> Iterator[dict[str, Any]]:
        for path in self.root.rglob("*.jsonl"):
            for rec in read_jsonl(path):
                yield {
                    "cobol_name": rec.get("cobol_name", ""),
                    "python_name": rec.get("python_name", ""),
                    "domain": rec.get("domain", "other"),
                    "confidence": rec.get("confidence", "MEDIUM"),
                }
