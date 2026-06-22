from __future__ import annotations

from src.utils.config import load_config


def test_loads_pipeline_config():
    cfg = load_config("pipeline")
    assert cfg.project.name == "parivartana"
    assert cfg.complexity_buckets.thresholds.simple_max == 12
    assert cfg.complexity_buckets.thresholds.medium_max == 28


def test_loads_datasets_config():
    cfg = load_config("datasets")
    assert "datasets" in cfg
    assert "nist_cobol" in cfg["datasets"]
    assert "ibm_open_cobol" in cfg["datasets"]
    assert len(cfg["datasets"]) == 9


def test_loads_models_config():
    cfg = load_config("models")
    assert "stage1_parser" in cfg
    assert "stage2_neural" in cfg
    assert "stage3_llm" in cfg
