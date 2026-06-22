
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.pipeline.stage1_parser.complexity import ComplexityTier
from src.pipeline.stage2_neural.curriculum import CurriculumScheduler
from src.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class ParallelExample:

    source_prompt: str                                         
    target_python: str
    tier: ComplexityTier
    source_id: str = ""


@dataclass
class TrainingConfig:
    backbone: str = "Salesforce/codet5p-220m"
    output_dir: str = "artifacts/checkpoints/codet5p_cobol"
    learning_rate: float = 5e-5
    weight_decay: float = 0.01
    warmup_ratio: float = 0.06
    batch_size: int = 16
    gradient_accumulation_steps: int = 4
    max_epochs: int = 20
    early_stopping_patience: int = 3
                                                                       
                                                                         
    fp16: bool = False
    bf16: bool = False
    seed: int = 42
    eval_metric: str = "codebleu_validation"
    curriculum_plateau_epochs: int = 3
    curriculum_pacing: str = "exponential"
                                                                     
                                                                      
    device: str = "auto"
    init_from: str | None = None
    peft: str = "none"
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    log_dir: str | None = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "TrainingConfig":
        import yaml

        with open(path, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        stage2 = cfg.get("stage2_neural", {})
        training = stage2.get("training", {})
        curriculum = stage2.get("curriculum", {})
        return cls(
            backbone=stage2.get("backbone", cls.backbone),
            learning_rate=float(training.get("learning_rate", cls.learning_rate)),
            weight_decay=float(training.get("weight_decay", cls.weight_decay)),
            warmup_ratio=float(training.get("warmup_ratio", cls.warmup_ratio)),
            batch_size=int(training.get("batch_size", cls.batch_size)),
            gradient_accumulation_steps=int(
                training.get("gradient_accumulation_steps", cls.gradient_accumulation_steps)
            ),
            max_epochs=int(training.get("max_epochs", cls.max_epochs)),
            early_stopping_patience=int(
                training.get("early_stopping_patience", cls.early_stopping_patience)
            ),
            fp16=bool(training.get("fp16", cls.fp16)),
            bf16=bool(training.get("bf16", cls.bf16)),
            device=str(training.get("device", cls.device)),
            curriculum_plateau_epochs=int(curriculum.get("plateau_epochs", cls.curriculum_plateau_epochs)),
            curriculum_pacing=curriculum.get("pacing", cls.curriculum_pacing),
        )


class CurriculumTrainer:

    def __init__(self, config: TrainingConfig) -> None:
        self.config = config
        self.scheduler = CurriculumScheduler(
            plateau_epochs=config.curriculum_plateau_epochs,
            pacing=config.curriculum_pacing,
        )
        self._history: list[dict] = []

                                                                        
    def dry_run(self, examples: list[ParallelExample], simulated_metrics: list[float]) -> list[dict]:
        tiers = [ex.tier for ex in examples]
        log_rows: list[dict] = []
        for epoch, metric in enumerate(simulated_metrics, start=1):
            active_tier = self.scheduler.step(metric)
            weights = self.scheduler.sample_weights(tiers)
            eligible = sum(1 for w in weights if w > 0)
            log_rows.append(
                {
                    "epoch": epoch,
                    "metric": metric,
                    "active_tier": active_tier.value,
                    "eligible_examples": eligible,
                    "total_examples": len(examples),
                }
            )
        self._history = log_rows
        return log_rows

    def save_history(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._history, indent=2))
        return path

                                                                        
    def run(self, train: list[ParallelExample], validation: list[ParallelExample]) -> Path:
        try:
            import torch              
            from datasets import Dataset
            from transformers import (
                AutoModelForSeq2SeqLM,
                AutoTokenizer,
                DataCollatorForSeq2Seq,
                EarlyStoppingCallback,
                Seq2SeqTrainer,
                Seq2SeqTrainingArguments,
            )
        except ImportError as exc:
            raise ImportError(
                "Full training requires `transformers`, `torch`, and `datasets`."
            ) from exc

                                                                     
        def _valid(examples: list[ParallelExample], split: str) -> list[ParallelExample]:
            ok = [ex for ex in examples if ex.source_prompt and ex.target_python]
            if not ok:
                raise ValueError(
                    f"No usable parallel examples in {split} split. "
                    "ParallelExample.source_prompt and .target_python must both "
                    "be non-empty strings. Linearise the Stage-1 AST as the "
                    "source and supply either a real Python translation or the "
                    "rule-based templater output as the target."
                )
            skipped = len(examples) - len(ok)
            if skipped:
                log.warning(f"{split}: skipped {skipped} examples with empty source/target")
            return ok

        train = _valid(train, "train")
        validation = _valid(validation, "validation")

        load_source = self.config.init_from or self.config.backbone
        if self.config.init_from:
            log.info(f"Continuing from checkpoint {self.config.init_from}")
        else:
            log.info(f"Loading backbone {self.config.backbone}")

        def _is_addedtoken_dict_error(exc: BaseException) -> bool:
            msg = str(exc)
            return (
                "List[Union[str, AddedToken]]" in msg
                or "must be either str or AddedToken" in msg
                or "Input must be a List" in msg
            )

        def _load_tokenizer(name: str):
                           
            try:
                return AutoTokenizer.from_pretrained(name)
            except (TypeError, ValueError) as exc:
                if not _is_addedtoken_dict_error(exc):
                    raise
                log.warning(
                    "tokenizer rejected legacy AddedToken dicts in "
                    "tokenizer_config.json (transformers 5.x); retrying "
                    "with use_fast=False"
                )

                                                                     
            try:
                return AutoTokenizer.from_pretrained(name, use_fast=False)
            except (TypeError, ValueError) as exc:
                if not _is_addedtoken_dict_error(exc):
                    raise
                log.warning(
                    "slow tokenizer also rejected the config; "
                    "materialising a patched local copy"
                )

                                         
            from src.pipeline.stage2_neural._tokenizer_patch import (
                materialise_clean_tokenizer,
            )

            patched_dir = materialise_clean_tokenizer(name)
            log.info(f"loading tokenizer from patched dir {patched_dir}")
                                                                           
                                              
            return AutoTokenizer.from_pretrained(str(patched_dir))

        try:
            tokenizer = _load_tokenizer(load_source)
            model = AutoModelForSeq2SeqLM.from_pretrained(load_source)
        except Exception as exc:                
            cause = f"{type(exc).__name__}: {exc}".splitlines()[0]
                                                                            
            extra_hint = ""
            if _is_addedtoken_dict_error(exc):
                extra_hint = (
                    "\nThis is the known transformers 5.x ↔ CodeT5+ tokenizer\n"
                    "incompatibility. The codet5p tokenizer_config.json serialises\n"
                    "special tokens as `__type: AddedToken` dicts, which the new\n"
                    "validator rejects. Parivartana ships an automatic patcher\n"
                    "(`src.pipeline.stage2_neural._tokenizer_patch`) that should\n"
                    "have kicked in — if you see this message, the patcher itself\n"
                    "failed (usually because HuggingFace is unreachable so the\n"
                    "tokenizer files could not be downloaded).\n"
                    "Workarounds:\n"
                    "  - Run `huggingface-cli download Salesforce/codet5p-220m` once\n"
                    "    while online to seed the HF cache, then retry.\n"
                    "  - Or switch backbone to `Salesforce/codet5-small` / `t5-small`\n"
                    "    in the Train tab (their tokenizer configs are clean).\n"
                    "  - Or pin: `pip install 'transformers==4.44.2' 'tokenizers<0.20'`.\n"
                )
            raise RuntimeError(
                f"Could not load backbone '{self.config.backbone}'. {cause}\n"
                "Common fixes:\n"
                "  - Run `huggingface-cli login` (or set HF_TOKEN) if the model is gated.\n"
                "  - Run `python -c \"from transformers import AutoTokenizer; "
                f"AutoTokenizer.from_pretrained('{self.config.backbone}')\"` once "
                "to warm the cache while online.\n"
                "  - For fully offline use, set HF_HUB_OFFLINE=1 and point "
                "HUGGINGFACE_HUB_CACHE at a directory that already contains the model."
                + extra_hint
            ) from exc

                                                                           
        from src.pipeline.stage2_neural.prompt_builder import SPECIAL_TOKENS

        vocab = tokenizer.get_vocab()
        new_tokens = [t for t in SPECIAL_TOKENS if t not in vocab]
        if new_tokens:
            try:
                tokenizer.add_special_tokens(
                    {"additional_special_tokens": list(new_tokens)}
                )
                model.resize_token_embeddings(len(tokenizer))
            except TypeError as exc:
                                                                        
                                                              
                try:
                    from transformers import AddedToken

                    wrapped = [AddedToken(t, special=True) for t in new_tokens]
                    tokenizer.add_special_tokens(
                        {"additional_special_tokens": wrapped}
                    )
                    model.resize_token_embeddings(len(tokenizer))
                except Exception as inner:                
                    raise RuntimeError(
                        f"Tokenizer rejected structural special tokens: {exc}. "
                        "Retry with `AddedToken` wrapper also failed: "
                        f"{inner}."
                    ) from inner

                                                                        
        try:
            tokenizer(["sanity check"], truncation=True, max_length=8)
        except Exception as exc:
            raise RuntimeError(
                f"Tokenizer pre-flight failed: {exc}. The configured backbone "
                f"'{self.config.backbone}' may have a corrupt tokenizer cache."
            ) from exc

        if (self.config.peft or "none").lower() == "lora":
            try:
                from peft import LoraConfig, TaskType, get_peft_model
            except ImportError as exc:
                raise ImportError(
                    "peft is required for --peft lora. Install it with "
                    "`pip install peft`."
                ) from exc
            lora_cfg = LoraConfig(
                task_type=TaskType.SEQ_2_SEQ_LM,
                r=self.config.lora_r,
                lora_alpha=self.config.lora_alpha,
                lora_dropout=self.config.lora_dropout,
                target_modules=["q", "k", "v", "o", "wi", "wo"],
            )
            model = get_peft_model(model, lora_cfg)
            trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
            total = sum(p.numel() for p in model.parameters())
            log.info(
                f"LoRA enabled (r={self.config.lora_r}, alpha={self.config.lora_alpha}): "
                f"{trainable:,} trainable / {total:,} total params "
                f"({100 * trainable / max(1, total):.2f}%)"
            )

                                                                            
        has_cuda = bool(getattr(torch, "cuda", None) and torch.cuda.is_available())
        has_mps = bool(
            getattr(torch, "backends", None)
            and getattr(torch.backends, "mps", None)
            and torch.backends.mps.is_available()
            and torch.backends.mps.is_built()
        )
        wanted = (self.config.device or "auto").lower()
        if wanted == "cpu":
            device_kind = "cpu"
        elif wanted == "cuda" and has_cuda:
            device_kind = "cuda"
        elif wanted == "mps" and has_mps:
            device_kind = "mps"
        elif wanted == "auto":
            device_kind = "cuda" if has_cuda else ("mps" if has_mps else "cpu")
        else:
            log.warning(
                f"requested device={wanted!r} not available "
                f"(cuda={has_cuda}, mps={has_mps}); falling back to CPU"
            )
            device_kind = "cpu"

                                                                            
        max_input_len = 1024
        max_output_len = 512
        per_device_batch = self.config.batch_size
        grad_accum = self.config.gradient_accumulation_steps
        eval_per_device_batch = self.config.batch_size
        gradient_checkpointing = False
                                                                         
                                                                        
        predict_with_generate = device_kind == "cuda"

        if device_kind == "mps":
                                                               
                                                                   
            effective_batch = max(1, per_device_batch * max(1, grad_accum))
            per_device_batch = 1
            grad_accum = effective_batch                                      
            eval_per_device_batch = 1
            max_input_len = min(max_input_len, 512)
            max_output_len = min(max_output_len, 256)
            gradient_checkpointing = True
            predict_with_generate = False
            log.info(
                "MPS profile applied: per_device_batch=1, "
                f"grad_accum={grad_accum} (effective batch {effective_batch}), "
                f"seq_len in/out={max_input_len}/{max_output_len}, "
                "gradient_checkpointing=True, predict_with_generate=False"
            )

        def encode(batch):
                                                                        
                                                                          
            sources = [s if isinstance(s, str) else "" for s in batch["source_prompt"]]
            targets = [s if isinstance(s, str) else "" for s in batch["target_python"]]
            inputs = tokenizer(
                sources,
                truncation=True,
                max_length=max_input_len,
                padding=False,
            )
            tgt = tokenizer(
                targets,
                truncation=True,
                max_length=max_output_len,
                padding=False,
            )
            inputs["labels"] = tgt["input_ids"]
            return inputs

        def _to_row(ex: ParallelExample) -> dict:
                                                                         
            return {
                "source_prompt": str(ex.source_prompt),
                "target_python": str(ex.target_python),
                "tier": ex.tier.value if hasattr(ex.tier, "value") else str(ex.tier),
                "source_id": str(ex.source_id),
            }

        train_ds = Dataset.from_list([_to_row(ex) for ex in train])
        eval_ds = Dataset.from_list([_to_row(ex) for ex in validation])
        keep = ["source_prompt", "target_python"]
        drop_train = [c for c in train_ds.column_names if c not in keep]
        drop_eval = [c for c in eval_ds.column_names if c not in keep]
        train_ds = train_ds.map(encode, batched=True, remove_columns=drop_train)
        eval_ds = eval_ds.map(encode, batched=True, remove_columns=drop_eval)

        out_dir = Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

                                                                        
        fp16 = bool(self.config.fp16) and device_kind == "cuda"
        bf16 = bool(self.config.bf16) and device_kind in {"cuda", "cpu"}
        if self.config.fp16 and device_kind != "cuda":
            log.warning(
                f"fp16=True but device is {device_kind!r}; disabling fp16 "
                "(it is a CUDA-only feature)."
            )

        log.info(
            f"training on device={device_kind} "
            f"(fp16={fp16}, bf16={bf16}, per_device_batch={per_device_batch}, "
            f"grad_accum={grad_accum})"
        )

                                                                     
        if gradient_checkpointing:
            try:
                model.gradient_checkpointing_enable()
                                                                
                                                                   
                if hasattr(model, "config"):
                    model.config.use_cache = False
            except Exception as exc:                
                log.warning(f"could not enable gradient checkpointing: {exc}")

                                                                            
        import inspect
        import math

                                                                      
        train_examples = int(getattr(train_ds, "num_rows", 0) or len(train))
        effective_batch = max(1, per_device_batch * max(1, grad_accum))
        steps_per_epoch = max(1, math.ceil(train_examples / effective_batch))
        total_optim_steps = steps_per_epoch * max(1, self.config.max_epochs)
        warmup_steps = int(round(self.config.warmup_ratio * total_optim_steps))

        ta_params = set(inspect.signature(Seq2SeqTrainingArguments.__init__).parameters)
                                                                   
                                                                         
        if predict_with_generate:
            metric_for_best = self.config.eval_metric
            greater_is_better = True
        else:
            metric_for_best = "eval_loss"
            greater_is_better = False

        ta_kwargs: dict = {
            "output_dir": str(out_dir),
            "learning_rate": self.config.learning_rate,
            "weight_decay": self.config.weight_decay,
            "per_device_train_batch_size": per_device_batch,
            "per_device_eval_batch_size": eval_per_device_batch,
            "gradient_accumulation_steps": grad_accum,
            "num_train_epochs": self.config.max_epochs,
            "fp16": fp16,
            "bf16": bf16,
            "save_strategy": "epoch",
            "save_total_limit": 2,                                             
            "load_best_model_at_end": True,
            "metric_for_best_model": metric_for_best,
            "greater_is_better": greater_is_better,
            "seed": self.config.seed,
            "predict_with_generate": predict_with_generate,
            "gradient_checkpointing": gradient_checkpointing,
                                                                         
                                                                   
            "dataloader_pin_memory": device_kind == "cuda",
        }

                                                                          
        if "eval_strategy" in ta_params:
            ta_kwargs["eval_strategy"] = "epoch"
        elif "evaluation_strategy" in ta_params:
            ta_kwargs["evaluation_strategy"] = "epoch"

                                                                           
        if "warmup_steps" in ta_params:
            ta_kwargs["warmup_steps"] = warmup_steps
            log.info(
                f"converted warmup_ratio={self.config.warmup_ratio} → "
                f"warmup_steps={warmup_steps} "
                f"(train_examples={train_examples}, effective_batch={effective_batch}, "
                f"epochs={self.config.max_epochs}, total_optim_steps={total_optim_steps})"
            )
        elif "warmup_ratio" in ta_params:
            ta_kwargs["warmup_ratio"] = self.config.warmup_ratio

                                                                             
        if device_kind == "cpu":
            if "use_cpu" in ta_params:
                ta_kwargs["use_cpu"] = True
            elif "no_cuda" in ta_params:
                ta_kwargs["no_cuda"] = True

                                                                        
        if device_kind == "mps" and "use_mps_device" in ta_params:
            ta_kwargs["use_mps_device"] = True

                                                                          
        ta_kwargs = {k: v for k, v in ta_kwargs.items() if k in ta_params}

        args = Seq2SeqTrainingArguments(**ta_kwargs)

                                                                            
        trainer_params = set(inspect.signature(Seq2SeqTrainer.__init__).parameters)
        callbacks: list = [
            EarlyStoppingCallback(
                early_stopping_patience=self.config.early_stopping_patience
            ),
        ]

                                                                     
        if device_kind == "mps":
            from transformers import TrainerCallback

            class _ClearMpsCacheCallback(TrainerCallback):

                def on_epoch_end(self, args, state, control, **kwargs):                       
                    try:
                                                                        
                        if hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
                            torch.mps.empty_cache()
                    except Exception:                
                        pass

            callbacks.append(_ClearMpsCacheCallback())

        trainer_kwargs: dict = {
            "model": model,
            "args": args,
            "train_dataset": train_ds,
            "eval_dataset": eval_ds,
            "data_collator": DataCollatorForSeq2Seq(tokenizer, model=model),
            "callbacks": callbacks,
        }
        if "processing_class" in trainer_params:                    
            trainer_kwargs["processing_class"] = tokenizer
        elif "tokenizer" in trainer_params:                    
            trainer_kwargs["tokenizer"] = tokenizer

        trainer = Seq2SeqTrainer(**trainer_kwargs)
                                                                      
                                                                   
        try:
            trainer.train()
        except RuntimeError as exc:
            msg = str(exc)
            if "out of memory" in msg.lower() or "MPS backend out of memory" in msg:
                                                                     
                                                                       
                raise RuntimeError(
                    f"Out of {device_kind.upper()} memory: {msg}\n\n"
                    f"Current MPS profile already uses per_device_batch={per_device_batch}, "
                    f"grad_accum={grad_accum}, max_input_len={max_input_len}, "
                    f"max_output_len={max_output_len}, gradient_checkpointing=True. "
                    f"To fit on this machine, reduce 'Programs per corpus' on the "
                    f"Train tab (start with 50), or set environment variable "
                    f"PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0 before launching the app "
                    f"(this disables the safety watermark — use with caution as it "
                    f"can hard-crash macOS under sustained memory pressure)."
                ) from exc
            raise
        trainer.save_model(str(out_dir))
                                                                 
                                                                         
        try:
            tokenizer.save_pretrained(str(out_dir))
        except Exception as exc:                
            log.warning(f"could not save tokenizer alongside checkpoint: {exc}")

                                                                     
        try:
            from src.pipeline.stage2_neural.checkpoint_registry import (
                make_record,
                record_latest,
            )

            rec = make_record(
                path=out_dir,
                backbone=self.config.backbone,
                dataset=self.config.metadata.get("dataset", "unknown"),
                train_examples=len(train),
                eval_examples=len(validation),
                epochs=self.config.max_epochs,
            )
            record_latest(rec)
            log.info(f"wrote latest-checkpoint pointer for {out_dir}")
        except Exception as exc:                
            log.warning(f"could not record latest checkpoint pointer: {exc}")
        return out_dir


def main() -> None:                                         
    import argparse

    parser = argparse.ArgumentParser(description="Stage 2 curriculum trainer")
    parser.add_argument("--config", default="configs/models.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Simulate scheduler without training")
    parser.add_argument("--train", help="path to train.jsonl from build_training_data.py")
    parser.add_argument("--val", help="path to val.jsonl (defaults to train dir's val.jsonl)")
    parser.add_argument("--init-from", default=None, help="checkpoint dir to continue training from")
    parser.add_argument("--peft", choices=["none", "lora"], default=None)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--backbone", default=None)
    args = parser.parse_args()

    cfg = TrainingConfig.from_yaml(args.config)
    if args.init_from:
        cfg.init_from = args.init_from
    if args.peft:
        cfg.peft = args.peft
    if args.epochs is not None:
        cfg.max_epochs = args.epochs
    if args.batch_size is not None:
        cfg.batch_size = args.batch_size
    if args.lr is not None:
        cfg.learning_rate = args.lr
    if args.output_dir:
        cfg.output_dir = args.output_dir
    if args.backbone:
        cfg.backbone = args.backbone
    trainer = CurriculumTrainer(cfg)

    if args.train:
        import json as _json

        def _load(path: str) -> list[ParallelExample]:
            rows = []
            for line in Path(path).read_text().splitlines():
                if not line.strip():
                    continue
                d = _json.loads(line)
                rows.append(ParallelExample(
                    source_prompt=d["source_prompt"],
                    target_python=d["target_python"],
                    tier=ComplexityTier(d["tier"]),
                    source_id=d.get("source_id", ""),
                ))
            return rows

        train_ex = _load(args.train)
        val_path = args.val or str(Path(args.train).with_name("val.jsonl"))
        val_ex = _load(val_path) if Path(val_path).exists() else []
        print(f"Training on {len(train_ex)} examples ({len(val_ex)} val) -> {cfg.output_dir}")
        out = trainer.run(train_ex, val_ex)
        print(f"Checkpoint saved to {out}")
        return

    if args.dry_run:
                                     
        rows = trainer.dry_run(
            examples=[
                ParallelExample(source_prompt="", target_python="", tier=ComplexityTier.SIMPLE),
                ParallelExample(source_prompt="", target_python="", tier=ComplexityTier.MEDIUM),
                ParallelExample(source_prompt="", target_python="", tier=ComplexityTier.HIGH),
            ],
            simulated_metrics=[0.10, 0.20, 0.20, 0.20, 0.20, 0.30, 0.30, 0.30, 0.30],
        )
        for row in rows:
            print(row)
        return
    raise SystemExit("Provide --dry-run, or import CurriculumTrainer for full training.")


if __name__ == "__main__":                    
    main()
