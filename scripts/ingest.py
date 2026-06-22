from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.ingestion import DatasetIngestor, build_adapter
from src.data.registry import DatasetRegistry
from src.utils.logging import get_logger

log = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest datasets for PARIVARTANA")
    p.add_argument("--dataset", help="Dataset key to ingest")
    p.add_argument(
        "--all",
        action="store_true",
        help="Ingest every auto-fetchable P0 dataset (the active set after the P3 scope cut)",
    )
    p.add_argument(
        "--priority",
        choices=["P0", "P1", "P2"],
        action="append",
        help="Restrict --all to datasets with this priority. Repeatable.",
    )
    p.add_argument(
        "--include-deferred",
        action="store_true",
        help="With --all, also pull P1 and P2 (deferred) datasets",
    )
    p.add_argument("--status", action="store_true", help="Print local status table and exit")
    p.add_argument("--list", action="store_true", help="List available datasets and exit")
    p.add_argument("--force", action="store_true", help="Re-download even if already present")
    return p.parse_args()


def cmd_list() -> int:
    registry = DatasetRegistry()
    print(f"{'KEY':<24} {'PRI':<4} {'METHOD':<16} {'NAME'}")
    print("-" * 88)
    for spec in registry.all():
        adapter = build_adapter(spec)
        print(f"{spec.key:<24} {spec.priority:<4} {adapter.method:<16} {spec.name}")
    return 0


def cmd_status() -> int:
    registry = DatasetRegistry()
    rows = registry.status_table()
    print(f"{'KEY':<24} {'PRI':<4} {'PRESENT':<8} {'FILES':<8} {'SIZE':<12} {'EXPECTED':<10}")
    print("-" * 88)
    for r in rows:
        size = _format_bytes(r["size_bytes"])
        present = "yes" if r["present"] else "no"
        print(
            f"{r['key']:<24} {r['priority']:<4} {present:<8} {r['files_on_disk']:<8} "
            f"{size:<12} {r['expected_samples']:<10,}"
        )
    return 0


def _format_bytes(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:,.1f} {unit}"
        size /= 1024
    return f"{size:,.1f} GB"


def _print_progress(message: str, fraction: float) -> None:
    bar = "#" * int(fraction * 30)
    print(f"\r[{bar:<30}] {fraction * 100:5.1f}%  {message}", end="", flush=True)


def cmd_one(key: str, force: bool) -> int:
    ingestor = DatasetIngestor()
    print(f"Ingesting: {key}")
    result = ingestor.ingest_one(key, progress=_print_progress, force=force)
    print()
    print(f"  Method  : {result.method}")
    print(f"  Success : {result.success}")
    print(f"  Records : {result.records_written:,}")
    print(f"  Size    : {_format_bytes(result.bytes_on_disk)}")
    print(f"  Message : {result.message}")
    return 0 if result.success else 1


def cmd_all(force: bool, priorities: set[str]) -> int:
    ingestor = DatasetIngestor()
    pr_label = ",".join(sorted(priorities))
    print(f"Ingesting datasets with priority in: {pr_label}")
    results = ingestor.ingest_all(progress=_print_progress, priorities=priorities)
    print()
    print()
    print(f"{'KEY':<24} {'OK':<6} {'METHOD':<16} {'RECORDS':<12} MESSAGE")
    print("-" * 100)
    failed = 0
    for r in results:
        status = "yes" if r.success else "no"
        print(f"{r.dataset_key:<24} {status:<6} {r.method:<16} {r.records_written:<12,} {r.message}")
        if not r.success:
            failed += 1
    return 0 if failed == 0 else 1


def main() -> int:
    args = parse_args()
    if args.list:
        return cmd_list()
    if args.status:
        return cmd_status()
    if args.all:
                                                                        
                                    
        if args.priority:
            priorities = set(args.priority)
        elif args.include_deferred:
            priorities = {"P0", "P1", "P2"}
        else:
            priorities = {"P0"}
        return cmd_all(force=args.force, priorities=priorities)
    if args.dataset:
        return cmd_one(args.dataset, force=args.force)
    print("No action specified. Use --dataset, --all, --status, or --list.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
