from __future__ import annotations

from typing import Any, Iterator

from src.data.loaders.base import BaseLoader
from src.utils.io import read_jsonl


class CodeXGlueLoader(BaseLoader):
    dataset_key = "codexglue"

    def iter_records(self) -> Iterator[dict[str, Any]]:
        for path in self.root.rglob("*.jsonl"):
            for rec in read_jsonl(path):
                yield {
                    "id": rec.get("id", ""),
                    "src_lang": rec.get("src_lang", "java"),
                    "tgt_lang": rec.get("tgt_lang", "python"),
                    "code": rec.get("code", ""),
                    "target": rec.get("target", ""),
                    "docstring": rec.get("docstring", ""),
                    "split": path.stem,
                }


class SweBenchLoader(BaseLoader):
    dataset_key = "swe_bench"

    def iter_records(self) -> Iterator[dict[str, Any]]:
        for path in self.root.rglob("*.jsonl"):
            for rec in read_jsonl(path):
                yield {
                    "instance_id": rec.get("instance_id", ""),
                    "repo": rec.get("repo", ""),
                    "issue_text": rec.get("problem_statement") or rec.get("issue_text", ""),
                    "patch": rec.get("patch", ""),
                    "test_cases": rec.get("test_patch", ""),
                    "split": path.stem,
                }
