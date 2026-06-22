
from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

                                                                             
_SINGLE_TOKEN_KEYS: tuple[str, ...] = (
    "bos_token",
    "eos_token",
    "unk_token",
    "sep_token",
    "pad_token",
    "cls_token",
    "mask_token",
)

                                       
_LIST_TOKEN_KEYS: tuple[str, ...] = ("additional_special_tokens",)


def _looks_like_added_token_dict(obj: Any) -> bool:
    return (
        isinstance(obj, dict)
        and ("content" in obj)
        and (obj.get("__type") == "AddedToken" or "lstrip" in obj or "rstrip" in obj)
    )


def _flatten_one(obj: Any) -> Any:
    if _looks_like_added_token_dict(obj):
        return obj["content"]
    return obj


def _patch_config_dict(cfg: dict[str, Any]) -> tuple[dict[str, Any], int]:
    edits = 0
    out: dict[str, Any] = {}
    for key, val in cfg.items():
        if key in _SINGLE_TOKEN_KEYS and _looks_like_added_token_dict(val):
            out[key] = _flatten_one(val)
            edits += 1
        elif key in _LIST_TOKEN_KEYS and isinstance(val, list):
            new_list = []
            for item in val:
                if _looks_like_added_token_dict(item):
                    new_list.append(_flatten_one(item))
                    edits += 1
                else:
                    new_list.append(item)
            out[key] = new_list
        else:
            out[key] = val
    return out, edits


def _patch_json_file(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warning("Could not parse %s; leaving untouched", path)
        return 0
    if not isinstance(cfg, dict):
        return 0
    patched, edits = _patch_config_dict(cfg)
    if edits:
        path.write_text(json.dumps(patched, indent=2), encoding="utf-8")
    return edits


def _local_target_dir(name: str, root: Path | None = None) -> Path:
    root = root or Path(
        os.environ.get("PARIVARTANA_TOKENIZER_CACHE")
        or (Path.home() / ".cache" / "parivartana" / "tokenizers")
    )
    safe = name.replace("/", "__")
    return root / safe


def materialise_clean_tokenizer(
    name: str, *, force: bool = False, target_root: Path | None = None
) -> Path:
    target = _local_target_dir(name, target_root)
    sentinel = target / ".parivartana_patched"
    if sentinel.exists() and not force:
        return target

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:                    
        raise RuntimeError(
            "materialise_clean_tokenizer requires `huggingface_hub`. "
            "Install it with `pip install huggingface_hub`."
        ) from exc

    target.mkdir(parents=True, exist_ok=True)

                                                                      
    snapshot = snapshot_download(
        repo_id=name,
        allow_patterns=[
            "tokenizer*.json",
            "special_tokens_map.json",
            "vocab.json",
            "merges.txt",
            "added_tokens.json",
            "spiece.model",
            "*.model",
            "*.spm",
        ],
    )

                                                                          
    for entry in Path(snapshot).iterdir():
        if entry.is_file():
            shutil.copy2(entry, target / entry.name)

    edits = 0
    edits += _patch_json_file(target / "tokenizer_config.json")
    edits += _patch_json_file(target / "special_tokens_map.json")

    log.info(
        "materialised patched tokenizer for %s at %s (edits=%d)", name, target, edits
    )
    sentinel.write_text(f"edits={edits}\n", encoding="utf-8")
    return target


def patch_existing_directory(directory: str | Path) -> int:
    d = Path(directory)
    return _patch_json_file(d / "tokenizer_config.json") + _patch_json_file(
        d / "special_tokens_map.json"
    )
