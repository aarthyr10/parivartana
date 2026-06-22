from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.theme import (
    badge,
    inject_global_styles,
    render_page_header,
    render_sidebar,
)
from src.pipeline.stage3_llm.providers import AnthropicProvider, OpenAIProvider
from src.utils.config import load_config
from src.utils.paths import CONFIG_DIR

st.set_page_config(page_title="Pipeline Config - PARIVARTANA", layout="wide")
inject_global_styles()
render_sidebar("Pipeline Config")


def main() -> None:
    render_page_header(eyebrow="CONFIGURATION", title="Pipeline Config")

    cfg_pipeline = load_config("pipeline")
    cfg_models = load_config("models")
    cfg_eval = load_config("evaluation")

    tabs = st.tabs(["Pipeline", "Stage 1", "Stage 2", "Stage 3", "Evaluation", "Providers"])

    with tabs[0]:
        st.code(yaml.safe_dump(cfg_pipeline.model_dump(), sort_keys=False), language="yaml")

    with tabs[1]:
        st.markdown(badge("Live", "success"), unsafe_allow_html=True)
        st.json(cfg_models["stage1_parser"])

    with tabs[2]:
        st.markdown(badge("In Progress", "warning"), unsafe_allow_html=True)
        st.json(cfg_models["stage2_neural"])

    with tabs[3]:
        st.markdown(badge("In Progress", "warning"), unsafe_allow_html=True)
        st.json(cfg_models["stage3_llm"])

    with tabs[4]:
        st.code(yaml.safe_dump(cfg_eval, sort_keys=False), language="yaml")

    with tabs[5]:
        oai = OpenAIProvider()
        ant = AnthropicProvider()
        rows = [
            {
                "Provider": "OpenAI",
                "Model": cfg_models["stage3_llm"]["providers"]["openai"]["model"],
                "Env var": "OPENAI_API_KEY",
                "Status": "Available" if oai.is_available() else "Key not set",
            },
            {
                "Provider": "Anthropic",
                "Model": cfg_models["stage3_llm"]["providers"]["anthropic"]["model"],
                "Env var": "ANTHROPIC_API_KEY",
                "Status": "Available" if ant.is_available() else "Key not set",
            },
        ]
        st.dataframe(rows, width="stretch", hide_index=True)

        st.markdown("**Filesystem**")
        st.json(
            {
                "config_dir": str(CONFIG_DIR),
                "checkpoints_dir": str(Path(cfg_pipeline.paths.checkpoints_dir)),
                "models_dir": str(Path(cfg_pipeline.paths.models_dir)),
                "gnucobol_path": os.getenv("GNUCOBOL_PATH", "cobc"),
            }
        )


main()
