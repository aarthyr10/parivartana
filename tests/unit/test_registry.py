from __future__ import annotations

from src.data.registry import DatasetRegistry


def test_registry_loads_all_nine_datasets():
    registry = DatasetRegistry()
    assert len(registry.keys()) == 9


def test_expected_dataset_keys_present():
    expected = {
        "nist_cobol",
        "ibm_open_cobol",
        "codexglue",
        "stack_v2_cobol",
        "cosqa_codesearchnet",
        "cobol_identifier_dict",
        "fever_nli",
        "swe_bench",
        "gfg_multilingual",
    }
    registry = DatasetRegistry()
    assert set(registry.keys()) == expected


def test_status_table_has_required_columns():
    registry = DatasetRegistry()
    rows = registry.status_table()
    required = {"key", "name", "role", "expected_samples", "license", "present"}
    for row in rows:
        assert required.issubset(row.keys())
