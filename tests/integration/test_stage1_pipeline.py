from __future__ import annotations

from pathlib import Path

from src.data.preprocess import CobolPreprocessor

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "data" / "samples"


def test_preprocess_runs_on_all_samples():
    preprocessor = CobolPreprocessor()
    records = []
    for path in sorted(SAMPLES.glob("*.cob")):
        records.append({"id": path.stem, "source": path.read_text(encoding="utf-8")})
    rows = preprocessor.process(records)
    assert len(rows) == len(records)
    assert all(r.parse_ok for r in rows)
    assert all(r.complexity_score >= 0 for r in rows)
