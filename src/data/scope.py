
from __future__ import annotations

from src.data.ingestion import build_adapter
from src.data.registry import DatasetRegistry, DatasetSpec

DEFAULT_ACTIVE_PRIORITIES: frozenset[str] = frozenset({"P0"})

                                                                     
TRAINABLE_KEYS: frozenset[str] = frozenset({"nist_cobol", "ibm_open_cobol"})


DATASET_USE: dict[str, str] = {
    "gold_evaluation": "TEST",
    "ood_evaluation": "TEST",
    "execution_evaluation": "TEST",
    "primary_training": "TRAIN",
    "transfer_pretraining": "TRAIN",
    "encoder_pretraining": "TRAIN",
    "docstring_identifier_generation": "SUPPORT",
    "semantic_validation": "SUPPORT",
    "identifier_renaming_lookup": "SUPPORT",
}

                                                                     
DATASET_USE_BADGE_KIND: dict[str, str] = {
    "TRAIN": "success",
    "TEST": "danger",
    "SUPPORT": "neutral",
}


def use_for(role: str) -> str:
    return DATASET_USE.get(role, "SUPPORT")


def use_for_with_kind(role: str) -> tuple[str, str]:
    use = use_for(role)
    return use, DATASET_USE_BADGE_KIND.get(use, "neutral")


def use_counts(specs) -> dict[str, int]:
    out = {"TRAIN": 0, "TEST": 0, "SUPPORT": 0}
    for spec in specs:
        out[use_for(spec.role)] = out.get(use_for(spec.role), 0) + 1
    return out


def active_specs(
    registry: DatasetRegistry,
    priorities: frozenset[str] | set[str] = DEFAULT_ACTIVE_PRIORITIES,
) -> list[DatasetSpec]:
    return [s for s in registry.all() if s.priority in priorities]


def auto_fetchable_specs(
    registry: DatasetRegistry,
    priorities: frozenset[str] | set[str] = DEFAULT_ACTIVE_PRIORITIES,
) -> list[DatasetSpec]:
    out: list[DatasetSpec] = []
    for spec in active_specs(registry, priorities):
        adapter = build_adapter(spec)
        if adapter.method != "manual":
            out.append(spec)
    return out


def trainable_specs(registry: DatasetRegistry) -> list[DatasetSpec]:
    return [
        s for s in active_specs(registry)
        if s.key in TRAINABLE_KEYS and s.exists_locally()
    ]
