from __future__ import annotations

import time

import pytest

from app.conversion_history import (
    ConversionRecord,
    clear_all,
    delete_conversion,
    list_conversions,
    load_conversion,
    new_record_id,
    save_conversion,
)


def _make(record_id: str | None = None, **overrides) -> ConversionRecord:
    base = {
        "record_id": record_id or new_record_id(),
        "created_at": time.time(),
        "program_id": "HELLO",
        "tier": "simple",
        "complexity_score": 1.2,
        "cobol_source": "       DISPLAY 'HI'.",
        "rule_based_python": "print('HI')\n",
        "neural_python": None,
        "refined_python": "print('HI')\n",
        "semantic_label": "SUPPORTED",
        "semantic_confidence": 0.9,
        "semantic_source": "lexical",
        "rename_count": 0,
        "pipeline_steps": ["rename:0", "llm_refine:no_provider", "semantic:SUPPORTED:lexical"],
        "stage_timings_ms": {"stage1_parse": 1.0, "stage2_rule_based": 0.5, "stage3_refine": 0.1},
        "provider": "openai",
        "fallback_used": False,
        "notes": "",
        "extra": {},
    }
    base.update(overrides)
    return ConversionRecord(**base)


def test_save_and_load_round_trip(tmp_path):
    rec = _make()
    path = save_conversion(rec, directory=tmp_path)
    assert path.exists()

    loaded = load_conversion(rec.record_id, directory=tmp_path)
    assert loaded is not None
    assert loaded.record_id == rec.record_id
    assert loaded.program_id == "HELLO"
    assert loaded.refined_python == "print('HI')\n"
    assert loaded.pipeline_steps == rec.pipeline_steps


def test_list_returns_newest_first(tmp_path):
    older = _make(program_id="OLD", created_at=time.time() - 100)
    newer = _make(program_id="NEW")
    save_conversion(older, directory=tmp_path)
    save_conversion(newer, directory=tmp_path)

    rows = list_conversions(directory=tmp_path)
    assert len(rows) == 2
    assert rows[0].program_id == "NEW"
    assert rows[1].program_id == "OLD"


def test_clear_all_removes_files(tmp_path):
    for _ in range(3):
        save_conversion(_make(), directory=tmp_path)
    assert len(list_conversions(directory=tmp_path)) == 3

    n = clear_all(directory=tmp_path)
    assert n == 3
    assert list_conversions(directory=tmp_path) == []
                                                                              
    assert tmp_path.exists()


def test_delete_single_record(tmp_path):
    keep = _make(program_id="KEEP")
    drop = _make(program_id="DROP")
    save_conversion(keep, directory=tmp_path)
    save_conversion(drop, directory=tmp_path)

    assert delete_conversion(drop.record_id, directory=tmp_path) is True
    remaining = list_conversions(directory=tmp_path)
    assert len(remaining) == 1
    assert remaining[0].program_id == "KEEP"


def test_load_missing_returns_none(tmp_path):
    assert load_conversion("nonexistent", directory=tmp_path) is None


def test_filename_is_sortable_and_slugged():
    rec = _make(program_id="PAY-ROLL CALC!")
    assert rec.filename.endswith(".json")
                                    
    assert "pay-roll_calc" in rec.filename.lower() or "pay_roll_calc" in rec.filename.lower()


def test_corrupt_file_is_skipped(tmp_path):
    good = _make()
    save_conversion(good, directory=tmp_path)
    (tmp_path / "garbage.json").write_text("{not json")

    rows = list_conversions(directory=tmp_path)
    assert len(rows) == 1
    assert rows[0].record_id == good.record_id


def test_from_dict_tolerates_missing_optional_fields():
    minimal = {"program_id": "X", "tier": "simple", "complexity_score": 0}
    rec = ConversionRecord.from_dict(minimal)
    assert rec.program_id == "X"
    assert rec.tier == "simple"
    assert rec.refined_python == ""
    assert rec.semantic_label == "not_run"
