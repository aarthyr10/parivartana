from __future__ import annotations

from src.data.ingestion import (
    GitHubCloneAdapter,
    HuggingFaceAdapter,
    ManualAdapter,
    ProjectAssetAdapter,
    build_adapter,
)
from src.data.registry import DatasetRegistry


def test_build_adapter_returns_huggingface_for_codexglue():
    spec = DatasetRegistry().get("codexglue")
    adapter = build_adapter(spec)
    assert isinstance(adapter, HuggingFaceAdapter)
    assert adapter.method == "huggingface"


def test_build_adapter_returns_github_for_gfg():
    spec = DatasetRegistry().get("gfg_multilingual")
    adapter = build_adapter(spec)
    assert isinstance(adapter, GitHubCloneAdapter)


def test_build_adapter_returns_manual_for_nist():
    spec = DatasetRegistry().get("nist_cobol")
    adapter = build_adapter(spec)
    assert isinstance(adapter, ManualAdapter)
    assert "NIST" in adapter.instructions


def test_build_adapter_returns_manual_for_ibm():
    spec = DatasetRegistry().get("ibm_open_cobol")
    adapter = build_adapter(spec)
    assert isinstance(adapter, ManualAdapter)


def test_build_adapter_returns_project_asset_for_dictionary():
    spec = DatasetRegistry().get("cobol_identifier_dict")
    adapter = build_adapter(spec)
    assert isinstance(adapter, ProjectAssetAdapter)


def test_manual_adapter_returns_failure_with_instructions():
    spec = DatasetRegistry().get("nist_cobol")
    adapter = build_adapter(spec)
    result = adapter.ingest()
    assert result.success is False
    assert result.method == "manual"
    assert "NIST" in result.message


def test_all_nine_datasets_have_an_adapter():
    registry = DatasetRegistry()
    for spec in registry.all():
        adapter = build_adapter(spec)
        assert adapter.method in {"huggingface", "github_clone", "manual", "project_asset"}
