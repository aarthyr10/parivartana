from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.theme import (
    inject_global_styles,
    render_page_header,
    render_sidebar,
)
from src.pipeline.stage3_llm.providers import AnthropicProvider, OpenAIProvider
from src.utils.paths import (
    ARTIFACTS_DIR,
    CHECKPOINTS_DIR,
    DATA_DIR,
    LOGS_DIR,
    MODELS_DIR,
    OUTPUTS_DIR,
    PROCESSED_DIR,
    PROJECT_ROOT,
    RAW_DIR,
    SAMPLES_DIR,
)

st.set_page_config(page_title="Settings - PARIVARTANA", layout="wide")
inject_global_styles()
render_sidebar("Settings")


def _check_dependency(name: str, import_name: str | None = None) -> dict:
    try:
        module = __import__(import_name or name)
        version = getattr(module, "__version__", "unknown")
        return {"Package": name, "Installed": "yes", "Version": version}
    except ImportError:
        return {"Package": name, "Installed": "no", "Version": "-"}


def main() -> None:
    render_page_header(eyebrow="SETTINGS", title="Settings")

    tabs = st.tabs(["Environment", "Paths", "Credentials", "Dependencies"])

    with tabs[0]:
        st.json(
            {
                "python_version": sys.version.split()[0],
                "platform": platform.platform(),
                "executable": sys.executable,
                "cwd": str(Path.cwd()),
            }
        )

    with tabs[1]:
        st.json(
            {
                "PROJECT_ROOT": str(PROJECT_ROOT),
                "DATA_DIR": str(DATA_DIR),
                "RAW_DIR": str(RAW_DIR),
                "PROCESSED_DIR": str(PROCESSED_DIR),
                "SAMPLES_DIR": str(SAMPLES_DIR),
                "ARTIFACTS_DIR": str(ARTIFACTS_DIR),
                "MODELS_DIR": str(MODELS_DIR),
                "CHECKPOINTS_DIR": str(CHECKPOINTS_DIR),
                "OUTPUTS_DIR": str(OUTPUTS_DIR),
                "LOGS_DIR": str(LOGS_DIR),
            }
        )

    with tabs[2]:
        credentials = [
            {
                "Variable": "OPENAI_API_KEY",
                "Set": "yes" if os.getenv("OPENAI_API_KEY") else "no",
            },
            {
                "Variable": "ANTHROPIC_API_KEY",
                "Set": "yes" if os.getenv("ANTHROPIC_API_KEY") else "no",
            },
            {
                "Variable": "HUGGINGFACE_TOKEN",
                "Set": "yes" if os.getenv("HUGGINGFACE_TOKEN") else "no",
            },
            {
                "Variable": "GNUCOBOL_PATH",
                "Set": os.getenv("GNUCOBOL_PATH") or "cobc",
            },
        ]
        st.dataframe(credentials, width="stretch", hide_index=True)

        st.markdown("**Providers**")
        oai_ok = OpenAIProvider().is_available()
        ant_ok = AnthropicProvider().is_available()
        provider_rows = [
            {"Provider": "openai", "Available": "yes" if oai_ok else "no"},
            {"Provider": "anthropic", "Available": "yes" if ant_ok else "no"},
        ]
        st.dataframe(provider_rows, width="stretch", hide_index=True)

    with tabs[3]:
        deps = [
            _check_dependency("streamlit"),
            _check_dependency("pandas"),
            _check_dependency("numpy"),
            _check_dependency("pyyaml", "yaml"),
            _check_dependency("pydantic"),
            _check_dependency("loguru"),
            _check_dependency("transformers"),
            _check_dependency("torch"),
            _check_dependency("datasets"),
            _check_dependency("openai"),
            _check_dependency("anthropic"),
        ]
        st.dataframe(deps, width="stretch", hide_index=True)


main()
