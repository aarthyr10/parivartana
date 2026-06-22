
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from src.utils.paths import CHECKPOINTS_DIR, ensure_dir

                                                                      
POINTER_PATH = CHECKPOINTS_DIR / "latest.json"


@dataclass
class CheckpointRecord:

    path: str                                                             
    backbone: str                                                 
    dataset: str                                               
    train_examples: int
    eval_examples: int
    epochs: int
    saved_at: float                   


def record_latest(record: CheckpointRecord) -> Path:
    ensure_dir(CHECKPOINTS_DIR)
    payload = asdict(record)
    POINTER_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return POINTER_PATH


def load_latest() -> CheckpointRecord | None:
    if not POINTER_PATH.exists():
        return None
    try:
        data = json.loads(POINTER_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return CheckpointRecord(**data)
    except TypeError:
                                                                  
                                
        keep = {k: data[k] for k in CheckpointRecord.__dataclass_fields__ if k in data}
        try:
            return CheckpointRecord(**keep)
        except TypeError:
            return None


def latest_path() -> Path | None:
    rec = load_latest()
    if rec is None:
        return None
    p = Path(rec.path)
    return p if p.exists() else None


def make_record(
    *,
    path: Path | str,
    backbone: str,
    dataset: str,
    train_examples: int,
    eval_examples: int,
    epochs: int,
) -> CheckpointRecord:
    return CheckpointRecord(
        path=str(Path(path).resolve()),
        backbone=backbone,
        dataset=dataset,
        train_examples=int(train_examples),
        eval_examples=int(eval_examples),
        epochs=int(epochs),
        saved_at=time.time(),
    )
