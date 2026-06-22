from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.utils.io import read_yaml
from src.utils.paths import CONFIG_DIR, PROJECT_ROOT


@dataclass
class DatasetSpec:
    key: str
    name: str
    role: str
    samples: int
    license: str
    source: dict[str, Any]
    local_path: Path
    splits: dict[str, Any] = field(default_factory=dict)
    metadata_fields: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
                                                            
                                                                      
    priority: str = "P0"

    def exists_locally(self) -> bool:
        if not self.local_path.exists():
            return False
        for p in self.local_path.rglob("*"):
            if p.is_file() and not p.name.startswith("."):
                return True
        return False

    def file_count(self) -> int:
        if not self.local_path.exists():
            return 0
        return sum(
            1
            for p in self.local_path.rglob("*")
            if p.is_file() and not p.name.startswith(".")
        )

    def disk_size_bytes(self) -> int:
        if not self.local_path.exists():
            return 0
        return sum(
            p.stat().st_size
            for p in self.local_path.rglob("*")
            if p.is_file() and not p.name.startswith(".")
        )


class DatasetRegistry:
    def __init__(self, config_name: str = "datasets") -> None:
        self.config_path = CONFIG_DIR / f"{config_name}.yaml"
        self._raw = read_yaml(self.config_path)
        self._specs: dict[str, DatasetSpec] = {}
        self._load_specs()

    def _load_specs(self) -> None:
        for key, raw in self._raw.get("datasets", {}).items():
            local = Path(raw["local_path"])
            if not local.is_absolute():
                local = PROJECT_ROOT / local
            spec = DatasetSpec(
                key=key,
                name=raw["name"],
                role=raw["role"],
                samples=raw["samples"],
                license=raw["license"],
                source=raw["source"],
                local_path=local,
                splits=raw.get("splits", {}),
                metadata_fields=raw.get("metadata_fields", []),
                priority=raw.get("priority", "P0"),
                extra={
                    k: v
                    for k, v in raw.items()
                    if k
                    not in {
                        "name",
                        "role",
                        "samples",
                        "license",
                        "source",
                        "local_path",
                        "splits",
                        "metadata_fields",
                        "priority",
                    }
                },
            )
            self._specs[key] = spec

    def keys(self) -> list[str]:
        return list(self._specs.keys())

    def get(self, key: str) -> DatasetSpec:
        if key not in self._specs:
            raise KeyError(f"Unknown dataset: {key}")
        return self._specs[key]

    def all(self) -> list[DatasetSpec]:
        return list(self._specs.values())

    def by_priority(self, priorities: set[str]) -> list[DatasetSpec]:
        return [s for s in self._specs.values() if s.priority in priorities]

    def status_table(self) -> list[dict[str, Any]]:
        rows = []
        for spec in self.all():
            rows.append(
                {
                    "key": spec.key,
                    "name": spec.name,
                    "role": spec.role,
                    "priority": spec.priority,
                    "expected_samples": spec.samples,
                    "license": spec.license,
                    "local_path": str(spec.local_path),
                    "present": spec.exists_locally(),
                    "files_on_disk": spec.file_count(),
                    "size_bytes": spec.disk_size_bytes(),
                }
            )
        return rows
