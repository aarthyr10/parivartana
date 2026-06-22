from __future__ import annotations

from typing import Any, Iterator

from src.data.loaders.base import BaseLoader
from src.utils.io import read_jsonl


class CoSqaCodeSearchNetLoader(BaseLoader):
    dataset_key = "cosqa_codesearchnet"

    def iter_records(self) -> Iterator[dict[str, Any]]:
        for path in self.root.rglob("*.jsonl"):
            for rec in read_jsonl(path):
                yield {
                    "intent": rec.get("intent") or rec.get("docstring", ""),
                    "code": rec.get("code", ""),
                    "func_name": rec.get("func_name", ""),
                    "language": rec.get("language", ""),
                    "split": path.stem,
                    "label": rec.get("label"),
                }
