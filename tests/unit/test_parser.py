from __future__ import annotations

from pathlib import Path

import pytest

from src.pipeline.stage1_parser import CobolParser

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "data" / "samples"


@pytest.mark.parametrize("sample_file", ["hello_world.cob", "payroll.cob", "sum_loop.cob"])
def test_parses_sample_programs(sample_file: str):
    source = (SAMPLES / sample_file).read_text(encoding="utf-8")
    parser = CobolParser()
    result = parser.parse(source)
    assert result.ok is True
    assert result.ast is not None
    assert result.division_count >= 1


def test_program_id_extracted():
    source = (SAMPLES / "payroll.cob").read_text(encoding="utf-8")
    result = CobolParser().parse(source)
    assert result.program_id.upper().startswith("PAYROLL")


def test_paragraphs_collected_for_loop_sample():
    source = (SAMPLES / "sum_loop.cob").read_text(encoding="utf-8")
    result = CobolParser().parse(source)
    assert result.paragraph_count >= 2
