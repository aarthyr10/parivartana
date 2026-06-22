from src.data.loaders.base import BaseLoader, LoaderResult
from src.data.loaders.cobol_corpus import (
    NistCobolLoader,
    IbmOpenCobolLoader,
    StackV2CobolLoader,
    GfgMultilingualLoader,
)
from src.data.loaders.parallel import CodeXGlueLoader, SweBenchLoader
from src.data.loaders.docstring import CoSqaCodeSearchNetLoader
from src.data.loaders.identifier_dict import CobolIdentifierDictLoader
from src.data.loaders.nli import FeverNliLoader

__all__ = [
    "BaseLoader",
    "LoaderResult",
    "NistCobolLoader",
    "IbmOpenCobolLoader",
    "StackV2CobolLoader",
    "GfgMultilingualLoader",
    "CodeXGlueLoader",
    "SweBenchLoader",
    "CoSqaCodeSearchNetLoader",
    "CobolIdentifierDictLoader",
    "FeverNliLoader",
    "ALL_LOADERS",
]


ALL_LOADERS = {
    "nist_cobol": NistCobolLoader,
    "ibm_open_cobol": IbmOpenCobolLoader,
    "codexglue": CodeXGlueLoader,
    "stack_v2_cobol": StackV2CobolLoader,
    "cosqa_codesearchnet": CoSqaCodeSearchNetLoader,
    "cobol_identifier_dict": CobolIdentifierDictLoader,
    "fever_nli": FeverNliLoader,
    "swe_bench": SweBenchLoader,
    "gfg_multilingual": GfgMultilingualLoader,
}
