from __future__ import annotations

import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from src.data.registry import DatasetRegistry, DatasetSpec
from src.utils.io import write_jsonl
from src.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class IngestionResult:
    dataset_key: str
    success: bool
    method: str
    records_written: int = 0
    bytes_on_disk: int = 0
    message: str = ""
    errors: list[str] = field(default_factory=list)


class IngestionAdapter(ABC):
    dataset_key: str = ""
    method: str = "abstract"

    def __init__(self, spec: DatasetSpec) -> None:
        self.spec = spec

    @property
    def target_dir(self) -> Path:
        return self.spec.local_path

    @abstractmethod
    def is_supported(self) -> bool: ...

    @abstractmethod
    def ingest(self, progress: Callable[[str, float], None] | None = None) -> IngestionResult: ...

    def already_present(self) -> bool:
        return self.spec.exists_locally()


class HuggingFaceAdapter(IngestionAdapter):
    method = "huggingface"

    def __init__(
        self,
        spec: DatasetSpec,
        repo: str,
        config: str | None = None,
        split: str | None = None,
        max_records: int | None = None,
        record_mapper: Callable[[dict], dict] | None = None,
        filter_fn: Callable[[dict], bool] | None = None,
        streaming: bool = False,
    ) -> None:
        super().__init__(spec)
        self.repo = repo
        self.config = config
        self.split = split
        self.max_records = max_records
        self.record_mapper = record_mapper
        self.filter_fn = filter_fn
        self.streaming = streaming

    def is_supported(self) -> bool:
        try:
            import datasets              
            return True
        except ImportError:
            return False

    def ingest(self, progress: Callable[[str, float], None] | None = None) -> IngestionResult:
        if not self.is_supported():
            return IngestionResult(
                self.spec.key,
                success=False,
                method=self.method,
                message="The 'datasets' package is not installed. Run: pip install datasets",
            )

        from datasets import load_dataset

        if progress:
            progress(f"Loading {self.repo} from HuggingFace...", 0.05)

        try:
            kwargs: dict = {}
            if self.config:
                kwargs["name"] = self.config
            if self.split:
                kwargs["split"] = self.split
            if self.streaming:
                kwargs["streaming"] = True
            ds = load_dataset(self.repo, **kwargs)
        except Exception as exc:
            return IngestionResult(
                self.spec.key,
                success=False,
                method=self.method,
                message=f"Download failed: {exc}",
                errors=[str(exc)],
            )

        self.target_dir.mkdir(parents=True, exist_ok=True)

                                                                          
        if hasattr(ds, "items"):
            split_iter = ds.items()
        else:
            split_iter = [(self.split or "train", ds)]

        total_written = 0
        for split_name, split_data in split_iter:
            records: list[dict] = []
                                                                           
            n = len(split_data) if hasattr(split_data, "__len__") else 0
            limit = self.max_records or (n if n else None)

            if progress:
                progress(f"Writing split '{split_name}'...", 0.3)

            kept = 0
            for i, row in enumerate(split_data):
                                                                             
                if self.filter_fn:
                    if not self.filter_fn(row):
                        continue
                else:
                    if limit and i >= limit:
                        break
                rec = dict(row)
                if self.record_mapper:
                    rec = self.record_mapper(rec)
                records.append(rec)
                kept += 1
                if progress and kept % 200 == 0:
                    progress(f"Scanned {i + 1:,}; kept {kept:,}", min(0.95, 0.3 + kept / (limit or 5000) * 0.6))
                if limit and kept >= limit:
                    break

            out_path = self.target_dir / f"{split_name}.jsonl"
            write_jsonl(out_path, records)
            total_written += len(records)
            log.info(f"Wrote {len(records)} records to {out_path}")

        if progress:
            progress("Complete", 1.0)

        return IngestionResult(
            self.spec.key,
            success=True,
            method=self.method,
            records_written=total_written,
            bytes_on_disk=self.spec.disk_size_bytes(),
            message=f"Downloaded {total_written} records to {self.target_dir}",
        )


class GitHubCloneAdapter(IngestionAdapter):
    method = "github_clone"

    def __init__(self, spec: DatasetSpec, repo_url: str, depth: int = 1) -> None:
        super().__init__(spec)
        self.repo_url = repo_url
        self.depth = depth

    def is_supported(self) -> bool:
        return shutil.which("git") is not None

    def ingest(self, progress: Callable[[str, float], None] | None = None) -> IngestionResult:
        if not self.is_supported():
            return IngestionResult(
                self.spec.key,
                success=False,
                method=self.method,
                message="git is not installed or not in PATH.",
            )

        if progress:
            progress(f"Cloning {self.repo_url}...", 0.1)

        self.target_dir.parent.mkdir(parents=True, exist_ok=True)

        if self.target_dir.exists() and any(
            p for p in self.target_dir.iterdir() if not p.name.startswith(".")
        ):
            return IngestionResult(
                self.spec.key,
                success=True,
                method=self.method,
                records_written=self.spec.file_count(),
                bytes_on_disk=self.spec.disk_size_bytes(),
                message=f"Already present at {self.target_dir}; skipping.",
            )

        if self.target_dir.exists():
            shutil.rmtree(self.target_dir)

        try:
            result = subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    str(self.depth),
                    self.repo_url,
                    str(self.target_dir),
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            return IngestionResult(
                self.spec.key,
                success=False,
                method=self.method,
                message="git clone timed out after 5 minutes.",
            )

        if result.returncode != 0:
            return IngestionResult(
                self.spec.key,
                success=False,
                method=self.method,
                message=f"git clone failed: {result.stderr.strip()}",
                errors=[result.stderr.strip()],
            )

        if progress:
            progress("Complete", 1.0)

        return IngestionResult(
            self.spec.key,
            success=True,
            method=self.method,
            records_written=self.spec.file_count(),
            bytes_on_disk=self.spec.disk_size_bytes(),
            message=f"Cloned to {self.target_dir}",
        )


class ManualAdapter(IngestionAdapter):
    method = "manual"

    def __init__(self, spec: DatasetSpec, instructions: str) -> None:
        super().__init__(spec)
        self.instructions = instructions

    def is_supported(self) -> bool:
        return True

    def ingest(self, progress: Callable[[str, float], None] | None = None) -> IngestionResult:
        return IngestionResult(
            self.spec.key,
            success=False,
            method=self.method,
            message=self.instructions,
        )


class ProjectAssetAdapter(IngestionAdapter):
    method = "project_asset"

    def is_supported(self) -> bool:
        return True

    def ingest(self, progress: Callable[[str, float], None] | None = None) -> IngestionResult:
        if self.already_present():
            return IngestionResult(
                self.spec.key,
                success=True,
                method=self.method,
                records_written=self.spec.file_count(),
                bytes_on_disk=self.spec.disk_size_bytes(),
                message=f"Project asset present at {self.target_dir}",
            )
        return IngestionResult(
            self.spec.key,
            success=False,
            method=self.method,
            message=(
                f"The project asset is missing from {self.target_dir}. "
                "Re-clone the repository or restore from backup."
            ),
        )


def _codexglue_mapper(rec: dict) -> dict:
    return {
        "id": rec.get("id", ""),
        "src_lang": "java",
        "tgt_lang": "cs",
        "code": rec.get("java", "") or rec.get("code", ""),
        "target": rec.get("cs", "") or rec.get("target", ""),
        "docstring": rec.get("docstring", ""),
    }


def _stack_v2_filter(rec: dict) -> bool:
    for key in ("language", "lang", "programming_language"):
        val = rec.get(key)
        if val and str(val).lower() in {"cobol", "cobolfree"}:
            return True
                                                    
    path = (rec.get("path") or rec.get("file_path") or "").lower()
    return path.endswith((".cob", ".cbl", ".cpy", ".cobol"))


def _stack_v2_mapper(rec: dict) -> dict:
    return {
        "id": rec.get("hexsha") or rec.get("blob_id") or rec.get("id") or "",
        "repo": rec.get("repo") or rec.get("repo_name") or "",
        "path": rec.get("path") or rec.get("file_path") or "",
        "license": rec.get("license") or rec.get("licenses") or "",
        "size": rec.get("size") or rec.get("length_bytes") or 0,
        "content": rec.get("content") or rec.get("text") or "",
    }


def _swe_bench_mapper(rec: dict) -> dict:
    return {
        "instance_id": rec.get("instance_id", ""),
        "repo": rec.get("repo", ""),
        "problem_statement": rec.get("problem_statement", ""),
        "patch": rec.get("patch", ""),
        "test_patch": rec.get("test_patch", ""),
        "base_commit": rec.get("base_commit", ""),
        "version": rec.get("version", ""),
    }


def build_adapter(spec: DatasetSpec) -> IngestionAdapter:
    key = spec.key

    if key == "codexglue":
        return HuggingFaceAdapter(
            spec,
            repo="google/code_x_glue_cc_code_to_code_trans",
            max_records=20000,
            record_mapper=_codexglue_mapper,
        )

    if key == "stack_v2_cobol":
                                                                          
                                                                    
        return HuggingFaceAdapter(
            spec,
            repo="bigcode/the-stack-smol",
            split="train",
            max_records=5000,
            filter_fn=_stack_v2_filter,
            record_mapper=_stack_v2_mapper,
            streaming=True,
        )

    if key == "cosqa_codesearchnet":
        return HuggingFaceAdapter(
            spec,
            repo="code_search_net",
            config="python",
            split="train",
            max_records=20000,
        )

    if key == "fever_nli":
        return HuggingFaceAdapter(
            spec,
            repo="fever",
            config="v1.0",
            split="train",
            max_records=50000,
        )

    if key == "swe_bench":
        return HuggingFaceAdapter(
            spec,
            repo="princeton-nlp/SWE-bench_Lite",
            split="test",
            max_records=300,
            record_mapper=_swe_bench_mapper,
        )

    if key == "gfg_multilingual":
        return GitHubCloneAdapter(
            spec,
            repo_url="https://github.com/TheAlgorithms/COBOL.git",
        )

    if key == "nist_cobol":
        return ManualAdapter(
            spec,
            instructions=(
                "The NIST COBOL Test Suite requires manual acquisition. "
                "1. Visit https://www.itl.nist.gov/div897/ctg/cobol_form.htm "
                "2. Download the Government COBOL Compiler Validation System (CCVS-85) tarball. "
                f"3. Extract under {spec.local_path}/."
            ),
        )

    if key == "ibm_open_cobol":
        return ManualAdapter(
            spec,
            instructions=(
                "IBM Open COBOL Samples require manual acquisition. "
                "1. Visit https://github.com/IBM/cobol-programming-course "
                "2. Clone the repository and copy the .cbl files from src/ "
                f"into {spec.local_path}/, optionally grouped by domain folder."
            ),
        )

    if key == "cobol_identifier_dict":
        return ProjectAssetAdapter(spec)

    raise ValueError(f"No ingestion adapter for dataset: {key}")


class DatasetIngestor:
    def __init__(self, registry: DatasetRegistry | None = None) -> None:
        self.registry = registry or DatasetRegistry()

    def ingest_one(
        self,
        dataset_key: str,
        progress: Callable[[str, float], None] | None = None,
        force: bool = False,
    ) -> IngestionResult:
        spec = self.registry.get(dataset_key)
        adapter = build_adapter(spec)

        if not force and adapter.already_present():
            return IngestionResult(
                dataset_key=dataset_key,
                success=True,
                method=adapter.method,
                records_written=spec.file_count(),
                bytes_on_disk=spec.disk_size_bytes(),
                message=f"Already present at {spec.local_path}. Pass force=True to re-download.",
            )

        log.info(f"Ingesting {dataset_key} via {adapter.method}")
        return adapter.ingest(progress=progress)

    def ingest_all(
        self,
        progress: Callable[[str, float], None] | None = None,
        skip_manual: bool = True,
        priorities: set[str] | None = None,
    ) -> list[IngestionResult]:
        priorities = priorities or {"P0"}
        results: list[IngestionResult] = []
        specs = [s for s in self.registry.all() if s.priority in priorities]
        for i, spec in enumerate(specs):
            key = spec.key
            adapter = build_adapter(spec)
            if skip_manual and adapter.method == "manual":
                results.append(
                    IngestionResult(
                        dataset_key=key,
                        success=False,
                        method=adapter.method,
                        message="Skipped (requires manual acquisition).",
                    )
                )
                continue
            if progress:
                progress(f"[{i + 1}/{len(specs)}] {spec.name}", i / max(1, len(specs)))
            results.append(self.ingest_one(key, force=False))
        if progress:
            progress("All datasets processed", 1.0)
        return results
