from __future__ import annotations

from typing import Any, Iterator

from src.data.loaders.base import BaseLoader
from src.utils.io import read_jsonl


class FeverNliLoader(BaseLoader):
    dataset_key = "fever_nli"

    def iter_records(self) -> Iterator[dict[str, Any]]:
        for path in self.root.rglob("*.jsonl"):
            for rec in read_jsonl(path):
                yield {
                    "id": rec.get("id"),
                    "claim": rec.get("claim", ""),
                    "label": rec.get("label", ""),
                    "evidence": rec.get("evidence", []),
                    "split": path.stem,
                }
