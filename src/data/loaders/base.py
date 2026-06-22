from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from src.data.registry import DatasetSpec


@dataclass
class LoaderResult:
    spec: DatasetSpec
    record_count: int
    sample_records: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""


class BaseLoader(ABC):
    dataset_key: str = ""

    def __init__(self, spec: DatasetSpec) -> None:
        self.spec = spec

    @property
    def root(self) -> Path:
        return self.spec.local_path

    def is_available(self) -> bool:
        return self.spec.exists_locally()

    @abstractmethod
    def iter_records(self) -> Iterator[dict[str, Any]]: ...

    def summarise(self, sample_size: int = 5) -> LoaderResult:
        if not self.is_available():
            return LoaderResult(
                spec=self.spec,
                record_count=0,
                notes=f"Not present at {self.spec.local_path}",
            )
        sample: list[dict[str, Any]] = []
        count = 0
        for record in self.iter_records():
            count += 1
            if len(sample) < sample_size:
                sample.append(record)
        return LoaderResult(
            spec=self.spec,
            record_count=count,
            sample_records=sample,
            notes="ok",
        )
