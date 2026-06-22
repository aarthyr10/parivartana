from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.theme import (
    badge,
    inject_global_styles,
    render_page_header,
    render_sidebar,
)
from src.data.ingestion import DatasetIngestor, build_adapter
from src.data.loaders import ALL_LOADERS
from src.data.preprocess import CobolPreprocessor
from src.data.registry import DatasetRegistry
from src.data.scope import (
    DEFAULT_ACTIVE_PRIORITIES,
    active_specs,
    auto_fetchable_specs,
    use_for_with_kind,
)
from src.pipeline.stage1_parser.complexity import ComplexityTier
from src.pipeline.stage1_parser.parser import CobolParser
from src.pipeline.stage2_neural.prompt_builder import PromptBuilder
from src.pipeline.stage2_neural.rule_based import RuleBasedTranslator
from src.pipeline.stage2_neural.training import CurriculumTrainer, ParallelExample, TrainingConfig
from src.utils.io import write_json
from src.utils.paths import ARTIFACTS_DIR, ensure_dir


_use_for = use_for_with_kind

st.set_page_config(page_title="Datasets - PARIVARTANA", layout="wide")
inject_global_styles()
render_sidebar("Datasets")


def _format_bytes(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:,.1f} {unit}"
        size /= 1024
    return f"{size:,.1f} GB"


def _method_badge(method: str) -> str:
    kinds = {
        "huggingface": "primary",
        "github_clone": "primary",
        "manual": "warning",
        "project_asset": "neutral",
    }
    labels = {
        "huggingface": "HuggingFace",
        "github_clone": "GitHub",
        "manual": "Manual",
        "project_asset": "Bundled",
    }
    return badge(labels.get(method, method), kinds.get(method, "neutral"))


def _present_badge(present: bool) -> str:
    return badge("Present", "success") if present else badge("Not ingested", "neutral")


def _dataset_overview_table(registry: DatasetRegistry, present_only: bool = True) -> pd.DataFrame:
    rows = []
    for spec in registry.all():
        present = spec.exists_locally()
        if present_only and not present:
            continue
        adapter = build_adapter(spec)
        use, _ = _use_for(spec.role)
        rows.append(
            {
                "Key": spec.key,
                "Name": spec.name,
                "Use": use,
                "Role": spec.role,
                "Method": adapter.method,
                "Expected": f"{spec.samples:,}",
                "License": spec.license,
                "Files": spec.file_count(),
                "Size": _format_bytes(spec.disk_size_bytes()),
            }
        )
    return pd.DataFrame(rows)


def _table_height(rows: int) -> int:
    return max(220, 38 + 35 * (rows + 1))


def main() -> None:
    render_page_header(eyebrow="DATASETS", title="Datasets")

    registry = DatasetRegistry()
    rows = registry.status_table()
    present = sum(1 for r in rows if r["present"])
    total_size = sum(r["size_bytes"] for r in rows)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Registered", len(rows))
    m2.metric("Present", present)
    m3.metric("Coverage", f"{(present / len(rows) * 100) if rows else 0:.0f}%")
    m4.metric("Disk usage", _format_bytes(total_size))

    st.markdown("<div class='pv-divider'></div>", unsafe_allow_html=True)

    tabs = st.tabs(["Overview", "Ingest", "Train", "Sample"])

    with tabs[0]:
                                                                          
                                                               
        missing_p0 = [
            s for s in registry.all()
            if s.priority == "P0" and not s.exists_locally()
        ]
        if missing_p0:
            cols = st.columns(min(3, len(missing_p0)))
            for col, spec in zip(cols, missing_p0):
                use, _ = _use_for(spec.role)
                col.warning(
                    f"**{spec.name}** ({use}) — not ingested.\n\n"
                    f"`{spec.key}` is P0 and feeds "
                    + (
                        "the Stage-3 NLI semantic validator."
                        if spec.key == "fever_nli"
                        else "the active pipeline."
                    )
                )

        show_all = st.toggle(
            "Show registered but not ingested",
            value=False,
            help="By default the table is filtered to datasets that have data on disk.",
        )
        overview_df = _dataset_overview_table(registry, present_only=not show_all)
        if overview_df.empty:
            st.info("No datasets are present yet. Go to the Ingest tab.")
        else:
            train_count = int((overview_df["Use"] == "TRAIN").sum())
            test_count = int((overview_df["Use"] == "TEST").sum())
            support_count = int((overview_df["Use"] == "SUPPORT").sum())
            st.markdown(
                f"<p style='color:#64748B;font-size:0.85rem;margin:0 0 0.5rem 0;'>"
                f"{len(overview_df)} present &middot; "
                f"{badge(f'{train_count} TRAIN', 'success')} &nbsp; "
                f"{badge(f'{test_count} TEST', 'danger')} &nbsp; "
                f"{badge(f'{support_count} SUPPORT', 'neutral')}"
                f"</p>",
                unsafe_allow_html=True,
            )
            st.dataframe(
                overview_df,
                width="stretch",
                hide_index=True,
                height=_table_height(len(overview_df)),
            )

    with tabs[1]:
        _render_ingest_tab(registry)

    with tabs[2]:
        _render_train_tab(registry)

    with tabs[3]:
        _render_sample_tab(registry)


def _render_ingest_tab(registry: DatasetRegistry) -> None:
                                                                       
                                                                     
    include_deferred = st.toggle(
        "Include deferred (P2) datasets",
        value=False,
        help=(
            "P2 datasets (the-stack-v2 COBOL, SWE-bench, GFG multilingual, "
            "CoSQA/CodeSearchNet) were descoped in the May proposal review. "
            "Turn on to expose them in the dropdown and bulk run."
        ),
        key="ingest_include_deferred",
    )
    priorities = frozenset({"P0", "P2"}) if include_deferred else DEFAULT_ACTIVE_PRIORITIES
    auto_specs = auto_fetchable_specs(registry, priorities)
    auto_keys = [s.key for s in auto_specs]

    col_a, col_b = st.columns([3, 2])

    with col_a:
        st.markdown("##### Single dataset")
        target_key = st.selectbox(
            "Dataset",
            options=auto_keys,
            format_func=lambda k: f"{registry.get(k).name} ({k})",
        )
        force = st.checkbox("Force re-ingest", value=False)
        target_spec = registry.get(target_key)
        target_adapter = build_adapter(target_spec)

        st.markdown(
            f"Method: {_method_badge(target_adapter.method)} &nbsp; "
            f"Local: {_present_badge(target_spec.exists_locally())}",
            unsafe_allow_html=True,
        )

        if st.button("Ingest dataset", type="primary", key="ingest_one"):
            ingestor = DatasetIngestor(registry)
            progress = st.progress(0.0, text="Starting...")

            def _update(msg: str, frac: float) -> None:
                progress.progress(min(frac, 1.0), text=msg)

            try:
                result = ingestor.ingest_one(target_key, progress=_update, force=force)
            except Exception as exc:
                progress.empty()
                st.error(f"Ingestion failed: {exc}")
                return

            progress.empty()
            if result.success:
                st.success(
                    f"{result.method} - {result.records_written:,} records, "
                    f"{_format_bytes(result.bytes_on_disk)}"
                )
            else:
                st.error(result.message)
                if result.errors:
                    with st.expander("Trace"):
                        for err in result.errors:
                            st.code(err)

    with col_b:
        st.markdown("##### Bulk (auto-fetchable only)")
        scope_label = "P0 + P2" if include_deferred else "P0 (active)"
        st.caption(
            f"{len(auto_keys)} auto-fetchable dataset(s) in scope ({scope_label}). "
            "Bulk run uses the same filter as this label."
        )
        if st.button("Ingest all", key="ingest_all", type="primary"):
            ingestor = DatasetIngestor(registry)
            overall = st.progress(0.0, text="Starting...")
            log_box = st.empty()

            def _bulk_update(msg: str, frac: float) -> None:
                overall.progress(min(frac, 1.0), text=msg)

            try:
                                                                    
                                                                
                results = ingestor.ingest_all(
                    progress=_bulk_update,
                    skip_manual=True,
                    priorities=set(priorities),
                )
            except Exception as exc:
                overall.empty()
                st.error(f"Bulk ingestion failed: {exc}")
                return

            overall.empty()
            df = pd.DataFrame(
                [
                    {
                        "Dataset": r.dataset_key,
                        "OK": "yes" if r.success else "no",
                        "Method": r.method,
                        "Records": f"{r.records_written:,}",
                        "Message": r.message,
                    }
                    for r in results
                    if r.method != "manual"
                ]
            )
            ok_count = sum(1 for r in results if r.success)
            st.success(f"{ok_count}/{len(df)} succeeded")
            log_box.dataframe(
                df,
                width="stretch",
                hide_index=True,
                height=_table_height(len(df)),
            )


def _prepare_examples(registry: DatasetRegistry, dataset_key: str, limit: int) -> tuple[list[ParallelExample], dict]:
    spec = registry.get(dataset_key)
    loader = ALL_LOADERS[dataset_key](spec)
    parser = CobolParser()
    scorer = __import__(
        "src.pipeline.stage1_parser.complexity", fromlist=["ComplexityScorer"]
    ).ComplexityScorer()
    templater = RuleBasedTranslator()
    prompt_builder = PromptBuilder()
    preprocessor = CobolPreprocessor()                                          

    examples: list[ParallelExample] = []
    tier_counts: dict[str, int] = {"simple": 0, "medium": 0, "high": 0}
    parsed_ok = 0
    parsed_fail = 0

    for idx, rec in enumerate(loader.iter_records(), start=1):
        if idx > limit:
            break
        source = rec.get("source") or rec.get("content") or ""
        record_id = rec.get("id") or f"rec_{idx}"
        parse = parser.parse(source)
        if not parse.ok or parse.ast is None:
            parsed_fail += 1
            continue
        parsed_ok += 1
        score = scorer.score(parse.ast)
        tier_counts[score.tier.value] = tier_counts.get(score.tier.value, 0) + 1

        prompt = prompt_builder.build(parse.ast, score.tier)
        target = templater.translate(parse.ast).code

        examples.append(
            ParallelExample(
                source_prompt=prompt.text,
                target_python=target,
                tier=score.tier,
                source_id=str(record_id),
            )
        )
    summary = {
        "parsed_ok": parsed_ok,
        "parsed_fail": parsed_fail,
        "tier_counts": tier_counts,
    }
    return examples, summary


def _synthetic_curve(epochs: int) -> list[float]:
    plateaus = [0.10, 0.18, 0.18, 0.18, 0.18, 0.32, 0.32, 0.32, 0.32, 0.50, 0.50, 0.50]
    if epochs <= len(plateaus):
        return plateaus[:epochs]
    return plateaus + [0.50] * (epochs - len(plateaus))


def _training_preflight(backbone: str = "Salesforce/codet5p-220m") -> dict:
    import importlib.util
    import socket

    def _has(mod: str) -> bool:
        return importlib.util.find_spec(mod) is not None

                                                                    
    network_ok = False
    try:
        with socket.create_connection(("huggingface.co", 443), timeout=2):
            network_ok = True
    except OSError:
        network_ok = False

                                                                       
    cache_root = Path(
        os.environ.get("HUGGINGFACE_HUB_CACHE")
        or os.environ.get("HF_HOME")
        or Path.home() / ".cache" / "huggingface"
    )
    if (cache_root / "hub").exists():
        cache_root = cache_root / "hub"
    repo_dir = "models--" + backbone.replace("/", "--")
    cached = list(cache_root.glob(f"**/{repo_dir}")) if cache_root.exists() else []

    return {
        "transformers": _has("transformers"),
        "torch": _has("torch"),
        "datasets": _has("datasets"),
        "hf_reachable": network_ok,
        "model_cached": bool(cached),
        "cache_root": str(cache_root),
        "backbone": backbone,
    }


_TRAIN_BACKBONE = "Salesforce/codet5p-220m"
                                                                          
                                                                         
_TRAINING_COBOL_DATASETS = ("nist_cobol", "ibm_open_cobol")


def _detect_training_device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"
    if getattr(torch, "cuda", None) and torch.cuda.is_available():
        return "cuda"
    backends = getattr(torch, "backends", None)
    if backends and getattr(backends, "mps", None) and backends.mps.is_available():
        return "mps"
    return "cpu"


def _split_examples(
    examples: list[ParallelExample], *, seed: int = 42, ratios: tuple[float, float, float] = (0.7, 0.15, 0.15)
) -> tuple[list[ParallelExample], list[ParallelExample], list[ParallelExample]]:
    import random
    from collections import defaultdict

    rng = random.Random(seed)
    by_tier: dict = defaultdict(list)
    for ex in examples:
        by_tier[ex.tier].append(ex)

    train: list[ParallelExample] = []
    valid: list[ParallelExample] = []
    test: list[ParallelExample] = []
    r_train, r_valid, _r_test = ratios
    for tier, items in by_tier.items():
        shuffled = items[:]
        rng.shuffle(shuffled)
        n = len(shuffled)
        n_train = max(1, int(round(n * r_train))) if n else 0
        n_valid = max(0, int(round(n * r_valid))) if n - n_train > 0 else 0
                                                                         
                                                                            
        if n_valid == 0 and n - n_train >= 1:
            n_valid = 1
        train.extend(shuffled[:n_train])
        valid.extend(shuffled[n_train : n_train + n_valid])
        test.extend(shuffled[n_train + n_valid :])
    return train, valid, test


def _render_train_tab(registry: DatasetRegistry) -> None:
    st.markdown(
        f"Fine-tune **{_TRAIN_BACKBONE}** on the ingested COBOL corpora. "
        "Training runs on CUDA, Apple Silicon (MPS), or CPU automatically — "
        "use the controls below to pick a corpus and start a real run, or "
        "the dry-run path to visualise the curriculum on a synthetic curve."
    )

    backbone = _TRAIN_BACKBONE
    device_kind = _detect_training_device()
    st.caption(
        f"Detected device: **{device_kind.upper()}** &nbsp;·&nbsp; "
        f"Backbone: `{backbone}` (only model with permissive license + "
        "CodeT5+ COBOL tokens that we currently train end-to-end)."
    )

                                                                        
    with st.expander("Environment pre-flight", expanded=False):
        pf = _training_preflight(backbone)
        st.caption("Dry-run works without any of these. Real fine-tune needs all four green.")
        rows: list[tuple[str, bool, str]] = [
            ("transformers installed", pf["transformers"], "pip install transformers"),
            ("torch installed", pf["torch"], "pip install torch  (CPU-only is fine for a demo)"),
            ("datasets installed", pf["datasets"], "pip install datasets"),
            (
                f"{backbone} cached or HuggingFace reachable",
                pf["model_cached"] or pf["hf_reachable"],
                f"first run pulls {backbone} into the HF cache",
            ),
        ]
        for name, ok, fix in rows:
            label = "READY" if ok else "MISSING"
            kind = "success" if ok else "warning"
            st.markdown(
                f"- {badge(label, kind)} &nbsp; **{name}** "
                + (f"<span style='color:#64748B;font-size:0.85rem;'>· {fix}</span>" if not ok else ""),
                unsafe_allow_html=True,
            )
        st.caption(
            f"HF cache root: `{pf['cache_root']}`. "
            "Use `huggingface-cli login` (or set HF_TOKEN in `.env`) if the model is gated."
        )

        if pf["transformers"] and pf["torch"] and not pf["model_cached"] and pf["hf_reachable"]:
            if st.button(f"Download {backbone} now", key="warm_cache"):
                with st.spinner(f"Pulling {backbone}..."):
                    try:
                        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

                        AutoTokenizer.from_pretrained(backbone)
                        AutoModelForSeq2SeqLM.from_pretrained(backbone)
                        st.success(f"{backbone} cached. The Run real fine-tune toggle will now use it offline.")
                    except Exception as exc:                
                        st.error(f"Download failed: {type(exc).__name__}: {exc}")

    runnable = [
        s for s in registry.all()
        if s.key in _TRAINING_COBOL_DATASETS and s.exists_locally() and s.key in ALL_LOADERS
    ]
    if not runnable:
        st.info(
            "No COBOL training corpus is present locally. Ingest "
            "`ibm_open_cobol` (and optionally `nist_cobol`) from the Ingest tab first."
        )
        return

                                                                   
    col_n, col_ep = st.columns(2)
    with col_n:
        limit = st.number_input(
            "Programs per corpus",
            min_value=10,
            max_value=2000,
            value=200,
            step=10,
            key="train_limit",
            help="Upper bound applied independently to each ingested corpus.",
        )
    with col_ep:
                                                                    
                                                                       
        epochs = st.number_input(
            "Epochs", min_value=3, max_value=40, value=6, step=1, key="train_epochs"
        )

    available_keys = [s.key for s in runnable]
    st.markdown(
        f"Will train on **{len(runnable)} corpus(es)**: "
        + ", ".join(f"`{k}`" for k in available_keys)
    )

    col_real, col_full, col_dry = st.columns(3)
    real_clicked = col_real.button(
        "Run real training",
        type="primary",
        key="train_real",
        width="stretch",
        help=(
            "Real fine-tune with the limits you set above. Auto-detects "
            "accelerator (CUDA → MPS → CPU). Saves a checkpoint and "
            "registers it so Batch Run can pick it up."
        ),
    )
    full_clicked = col_full.button(
        "Run FULL training",
        type="primary",
        key="train_full",
        width="stretch",
        help=(
            "End-to-end fine-tune across EVERY parseable program from every "
            "ingested COBOL corpus (no per-corpus cap), 20 epochs, "
            "early-stopping disabled. May run for hours on CPU/MPS — uses "
            "the auto-detected accelerator and registers the resulting "
            "checkpoint so Batch Run can pick it up immediately."
        ),
    )
    dry_clicked = col_dry.button(
        "Run curriculum dry-run",
        type="secondary",
        key="train_dry",
        width="stretch",
        help=(
            "Walks the curriculum scheduler against a synthetic plateauing "
            "metric. No model weights touched."
        ),
    )

    if real_clicked or full_clicked or dry_clicked:
        import sys as _sys

        if full_clicked:
            effective_limit = _sys.maxsize
            effective_epochs = 20
            effective_early_stop = 9_999
            st.info(
                "FULL training: every parseable program from every ingested COBOL "
                f"corpus (no cap), {effective_epochs} epochs, early-stopping disabled. "
                "Expect a long run on CPU/MPS — keep the tab open."
            )
        else:
            effective_limit = int(limit)
            effective_epochs = int(epochs)
            effective_early_stop = 3

        all_examples: list[ParallelExample] = []
        per_corpus_summary: dict[str, dict] = {}
        with st.spinner("Loading and preprocessing..."):
            for spec in runnable:
                ex_list, sub_summary = _prepare_examples(registry, spec.key, effective_limit)
                                                                      
                for ex in ex_list:
                    ex.source_id = f"{spec.key}:{ex.source_id}"
                all_examples.extend(ex_list)
                per_corpus_summary[spec.key] = sub_summary

        if not all_examples:
            st.error("No parseable programs across the selected corpora.")
            return
        examples = all_examples
        summary = {
            "parsed_ok": sum(s["parsed_ok"] for s in per_corpus_summary.values()),
            "parsed_fail": sum(s["parsed_fail"] for s in per_corpus_summary.values()),
            "tier_counts": {
                t: sum(s["tier_counts"].get(t, 0) for s in per_corpus_summary.values())
                for t in ("simple", "medium", "high")
            },
        }
        dataset_key = "+".join(available_keys)

                                                                          
        st.markdown("##### Data prepared")
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Parsed", summary["parsed_ok"])
        d2.metric("Simple", summary["tier_counts"].get("simple", 0))
        d3.metric("Medium", summary["tier_counts"].get("medium", 0))
        d4.metric("High", summary["tier_counts"].get("high", 0))

                                                                          
        train_set, valid_set, test_set = _split_examples(examples)
        s1, s2, s3 = st.columns(3)
        s1.metric("Train", len(train_set))
        s2.metric("Valid", len(valid_set))
        s3.metric("Test", len(test_set))

                                                                          
        config = TrainingConfig(
            backbone=backbone,
            max_epochs=effective_epochs,
            early_stopping_patience=effective_early_stop,
            curriculum_plateau_epochs=2,
            curriculum_pacing="exponential",
            device="auto",
            metadata={"dataset": dataset_key, "mode": "full" if full_clicked else "real"},
        )
        trainer = CurriculumTrainer(config)
        real_train = False

        if real_clicked or full_clicked:
            st.markdown("##### Real fine-tune")
            with st.spinner(
                f"Running real fine-tune on {device_kind.upper()}... "
                "this may take a few minutes per epoch on M2"
            ):
                try:
                    out_dir = trainer.run(train_set, valid_set)
                    st.success(
                        f"Checkpoint saved to `{out_dir}` — Batch Run can now load it."
                    )
                    real_train = True
                except ImportError as exc:
                    st.error(
                        f"Real fine-tune unavailable: {exc}. "
                        "Install transformers + torch + datasets, or run the dry-run instead."
                    )
                except Exception as exc:                
                    st.error(f"Fine-tune failed: {exc}. Showing dry-run instead.")

                                                                         
        st.markdown("##### Curriculum dry-run")
        curve = _synthetic_curve(effective_epochs)
                                                       
        trainer = CurriculumTrainer(config)
        history = trainer.dry_run(examples, curve)

        history_df = pd.DataFrame(history)
        history_df["tier_rank"] = history_df["active_tier"].map(
            {"simple": 1, "medium": 2, "high": 3}
        )

        c1, c2 = st.columns(2)
        with c1:
            st.caption("Validation metric vs epoch (synthetic plateauing curve)")
            st.line_chart(history_df, x="epoch", y="metric", height=240, width="stretch")
        with c2:
            st.caption("Eligible examples released per epoch")
            st.area_chart(history_df, x="epoch", y="eligible_examples", height=240, width="stretch")

        st.caption("Active curriculum tier per epoch (1=Simple, 2=Medium, 3=High)")
        st.line_chart(history_df, x="epoch", y="tier_rank", height=200, width="stretch")

        st.dataframe(
            history_df[["epoch", "metric", "active_tier", "eligible_examples", "total_examples"]],
            width="stretch",
            hide_index=True,
            height=_table_height(len(history_df)),
        )

                                       
        history_path = ensure_dir(ARTIFACTS_DIR / "training") / f"history_{dataset_key}_{int(time.time())}.json"
        write_json(
            history_path,
            {
                "dataset": dataset_key,
                "epochs": int(epochs),
                "config": {
                    "max_epochs": config.max_epochs,
                    "plateau_epochs": config.curriculum_plateau_epochs,
                    "pacing": config.curriculum_pacing,
                },
                "data_summary": summary,
                "history": history,
                "real_train": bool(real_train),
            },
        )
        st.success(f"Saved training history to `{history_path.relative_to(ROOT)}`")


def _render_sample_tab(registry: DatasetRegistry) -> None:
    available = [s for s in registry.all() if s.exists_locally() and s.key in ALL_LOADERS]
    if not available:
        st.info("No datasets present.")
        return

    col_a, col_b = st.columns([2, 1])
    with col_a:
        selected = st.selectbox(
            "Dataset",
            options=[s.key for s in available],
            format_func=lambda k: registry.get(k).name,
        )
    with col_b:
        sample_size = st.slider("Sample size", 1, 20, 5)

    spec = registry.get(selected)
    loader = ALL_LOADERS[selected](spec)

    if st.button("Read sample"):
        with st.spinner("Reading..."):
            result = loader.summarise(sample_size=sample_size)
        cols = st.columns(3)
        cols[0].metric("Records", f"{result.record_count:,}")
        cols[1].metric("Files", spec.file_count())
        cols[2].metric("Disk usage", _format_bytes(spec.disk_size_bytes()))

        if result.sample_records:
            for i, rec in enumerate(result.sample_records, start=1):
                with st.expander(f"Record {i}"):
                    st.json(rec)
        else:
            st.warning("No records read.")


main()
