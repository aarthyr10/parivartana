from __future__ import annotations

from src.pipeline.stage3_llm.renamer import IdentifierRenamer


def test_strips_working_storage_prefix():
    renamer = IdentifierRenamer()
    mapping = renamer.rename("WS-EMPLOYEE-NAME")
    assert "employee" in mapping.python_name
    assert "name" in mapping.python_name


def test_maps_amt_suffix_to_amount():
    renamer = IdentifierRenamer()
    mapping = renamer.rename("WS-ACCT-BAL-AMT")
    assert mapping.python_name.endswith("amount")


def test_unknown_suffix_passes_through():
    renamer = IdentifierRenamer()
    mapping = renamer.rename("WS-CUSTOMER")
    assert mapping.python_name == "customer"


def test_low_confidence_for_rule_based():
    renamer = IdentifierRenamer()
    mapping = renamer.rename("WS-FOO")
    assert mapping.confidence == "LOW"
    assert mapping.source == "rule"
