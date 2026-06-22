from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.loaders import ALL_LOADERS
from src.data.preprocess import CobolPreprocessor
from src.data.registry import DatasetRegistry
from src.utils.io import write_jsonl
from src.utils.logging import get_logger
from src.utils.paths import PROCESSED_DIR, ensure_dir

log = get_logger(__name__)

COBOL_DATASETS = {"nist_cobol", "ibm_open_cobol", "stack_v2_cobol", "gfg_multilingual"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Preprocess COBOL datasets through Stage 1")
    p.add_argument("--dataset", required=True, help="Dataset key")
    p.add_argument("--limit", type=int, default=0, help="Max records (0 = all)")
    p.add_argument("--out", default=None, help="Output JSONL path (defaults under data/processed/)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    registry = DatasetRegistry()
    spec = registry.get(args.dataset)

    if args.dataset not in COBOL_DATASETS:
        log.error(f"Preprocessing only supports COBOL corpora: {sorted(COBOL_DATASETS)}")
        return 2

    loader = ALL_LOADERS[args.dataset](spec)
    if not loader.is_available():
        log.error(f"Dataset not present at {spec.local_path}")
        return 1

    preprocessor = CobolPreprocessor()
    rows: list[dict] = []
    t0 = time.perf_counter()
    for idx, rec in enumerate(loader.iter_records(), start=1):
        if args.limit and idx > args.limit:
            break
        processed = preprocessor.process_record(rec)
        rows.append(
            {
                "id": processed.id,
                "tier": processed.tier.value,
                "complexity_score": processed.complexity_score,
                "ast_depth": processed.ast_depth,
                "unique_verb_count": processed.unique_verb_count,
                "cross_ref_count": processed.cross_ref_count,
                "high_tier_flag": processed.high_tier_flag,
                "parse_ok": processed.parse_ok,
                "error_count": processed.error_count,
            }
        )

    ensure_dir(PROCESSED_DIR)
    out_path = Path(args.out) if args.out else PROCESSED_DIR / f"{args.dataset}.jsonl"
    write_jsonl(out_path, rows)
    log.info(f"Wrote {len(rows)} records to {out_path} in {time.perf_counter() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
