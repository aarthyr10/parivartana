
from __future__ import annotations

import os
import threading

_patched = False


def _install_env_flag() -> None:
    os.environ.setdefault("DISABLE_SAFETENSORS_CONVERSION", "1")


def _install_threading_excepthook() -> None:
    prev = threading.excepthook

    def _hook(args: threading.ExceptHookArgs) -> None:
        thread = getattr(args, "thread", None)
        name = getattr(thread, "name", "") if thread else ""
        if isinstance(name, str) and name.startswith("Thread-auto_conversion"):
            return
        prev(args)

    threading.excepthook = _hook


def _patch_function_references() -> None:

    def _noop_auto_conversion(*args, **kwargs):                              
                                                                       
                                                                      
        return None, "main", False

    try:
        from transformers import safetensors_conversion                              

        safetensors_conversion.auto_conversion = _noop_auto_conversion                            
    except (ImportError, AttributeError):
        pass

                                                                     
    try:
        from transformers import modeling_utils                              

        if hasattr(modeling_utils, "auto_conversion"):
            modeling_utils.auto_conversion = _noop_auto_conversion                            
    except (ImportError, AttributeError):
        pass


def apply() -> None:
    global _patched
    if _patched:
        return
    _patched = True
                                                                       
                                                                      
    _install_env_flag()
    _install_threading_excepthook()
    _patch_function_references()


apply()
