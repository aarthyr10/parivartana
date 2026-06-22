from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default="artifacts/checkpoints/codet5p_cobol")
    ap.add_argument("--out", default="artifacts/checkpoints/codet5p_cobol_merged")
    ap.add_argument("--base", default=None)
    a = ap.parse_args()

    from peft import PeftModel
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    adapter_cfg = json.loads((Path(a.adapter) / "adapter_config.json").read_text())
    base = a.base or adapter_cfg.get("base_model_name_or_path") or "Salesforce/codet5p-220m"
    print(f"base = {base}")
    print(f"adapter = {a.adapter}")

    try:
        model = AutoModelForSeq2SeqLM.from_pretrained(base, local_files_only=True)
    except (OSError, EnvironmentError) as exc:
        print(f"safetensors load failed ({type(exc).__name__}); retrying use_safetensors=False")
        model = AutoModelForSeq2SeqLM.from_pretrained(
            base, local_files_only=True, use_safetensors=False
        )
    tok = AutoTokenizer.from_pretrained(a.adapter)
    if len(tok) != model.get_input_embeddings().weight.shape[0]:
        model.resize_token_embeddings(len(tok), mean_resizing=False)

    model = PeftModel.from_pretrained(model, a.adapter)
    model = model.merge_and_unload()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out))
    tok.save_pretrained(str(out))
    print(f"merged full model saved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
