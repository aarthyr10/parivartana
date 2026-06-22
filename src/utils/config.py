from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from src.utils.paths import CONFIG_DIR


class ProjectMeta(BaseModel):
    name: str
    version: str
    seed: int = 42


class PathsConfig(BaseModel):
    data_dir: str
    raw_dir: str
    interim_dir: str
    processed_dir: str
    samples_dir: str
    artifacts_dir: str
    models_dir: str
    checkpoints_dir: str
    outputs_dir: str
    logs_dir: str


class ComplexityWeights(BaseModel):
    ast_depth: float
    unique_verb_count: float
    cross_ref_count: float
    high_tier_flag: float


class ComplexityThresholds(BaseModel):
    simple_max: int
    medium_max: int


class ComplexityBuckets(BaseModel):
    weights: ComplexityWeights
    thresholds: ComplexityThresholds
    expected_distribution: dict[str, float]


class ProjectConfig(BaseModel):
    project: ProjectMeta
    paths: PathsConfig
    pipeline: dict[str, Any]
    complexity_buckets: ComplexityBuckets
    preprocessing: dict[str, Any]
    logging: dict[str, Any] = Field(default_factory=dict)


def _read_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=8)
def load_config(name: str = "pipeline") -> ProjectConfig | dict[str, Any]:
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    raw = _read_yaml(path)
    if name == "pipeline":
        return ProjectConfig(**raw)
    return raw


def reload_config(name: str = "pipeline") -> ProjectConfig | dict[str, Any]:
    load_config.cache_clear()
    return load_config(name)
