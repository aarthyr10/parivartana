from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import streamlit as st

                                                                     
def _autoload_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
                                                                     
                                             
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


_autoload_env()

PRIMARY = "#4F46E5"
PRIMARY_LIGHT = "#EEF2FF"
SUCCESS = "#16A34A"
SUCCESS_LIGHT = "#DCFCE7"
WARNING = "#D97706"
WARNING_LIGHT = "#FEF3C7"
DANGER = "#DC2626"
DANGER_LIGHT = "#FEE2E2"
NEUTRAL = "#475569"
NEUTRAL_LIGHT = "#F1F5F9"
BORDER = "#E2E8F0"


GLOBAL_CSS = f"""
<style>
:root {{
    --pv-primary: {PRIMARY};
    --pv-primary-light: {PRIMARY_LIGHT};
    --pv-border: {BORDER};
    --pv-text-muted: #64748B;
    --pv-header-height: 3.75rem;
}}

header[data-testid="stHeader"] {{
    background: #FFFFFF;
    border-bottom: 1px solid var(--pv-border);
    height: var(--pv-header-height);
    z-index: 999;
}}

[data-testid="stAppViewContainer"] > .main,
section[data-testid="stMain"] {{
    padding-top: var(--pv-header-height);
}}

.block-container {{
    padding-top: 2.5rem;
    padding-bottom: 3rem;
    max-width: 1280px;
}}

[data-testid="stSidebar"] {{
    background-color: #FAFBFC;
    border-right: 1px solid var(--pv-border);
    padding-top: var(--pv-header-height);
}}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {{
    color: var(--pv-primary);
}}

[data-testid="stSidebarNav"] ul li a span,
[data-testid="stSidebarNav"] a span {{
    text-transform: capitalize;
    font-weight: 500;
}}

.pv-brand {{
    font-family: Georgia, "Times New Roman", serif;
    font-size: 1.6rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    color: var(--pv-primary);
    margin: 0;
}}

.pv-tagline {{
    font-size: 0.78rem;
    color: var(--pv-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 0.5rem;
}}

.pv-eyebrow {{
    font-size: 0.72rem;
    color: var(--pv-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-weight: 600;
    margin-bottom: 0.25rem;
}}

.pv-page-title {{
    font-size: 2rem;
    font-weight: 700;
    color: #0F172A;
    margin: 0 0 0.4rem 0;
    letter-spacing: -0.02em;
}}

.pv-page-subtitle {{
    color: var(--pv-text-muted);
    font-size: 1rem;
    margin: 0 0 1.5rem 0;
}}

.pv-card {{
    background: #FFFFFF;
    border: 1px solid var(--pv-border);
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
}}

.pv-card-title {{
    font-size: 0.85rem;
    font-weight: 600;
    color: #0F172A;
    margin: 0 0 0.5rem 0;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}}

.pv-stat-value {{
    font-size: 1.8rem;
    font-weight: 700;
    color: #0F172A;
    line-height: 1.1;
}}

.pv-stat-label {{
    font-size: 0.78rem;
    color: var(--pv-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 0.3rem;
}}

.pv-badge {{
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    line-height: 1.4;
}}

.pv-badge-success {{ background: {SUCCESS_LIGHT}; color: {SUCCESS}; }}
.pv-badge-warning {{ background: {WARNING_LIGHT}; color: {WARNING}; }}
.pv-badge-danger  {{ background: {DANGER_LIGHT};  color: {DANGER};  }}
.pv-badge-neutral {{ background: {NEUTRAL_LIGHT}; color: {NEUTRAL}; }}
.pv-badge-primary {{ background: {PRIMARY_LIGHT}; color: {PRIMARY}; }}

.pv-stage-row {{
    display: flex;
    gap: 1rem;
    margin: 0.75rem 0 1.5rem 0;
}}

.pv-stage {{
    flex: 1;
    background: #FFFFFF;
    border: 1px solid var(--pv-border);
    border-radius: 10px;
    padding: 1rem 1.2rem;
}}

.pv-stage-num {{
    font-size: 0.7rem;
    font-weight: 700;
    color: var(--pv-text-muted);
    letter-spacing: 0.12em;
}}

.pv-stage-name {{
    font-size: 1rem;
    font-weight: 600;
    color: #0F172A;
    margin: 0.2rem 0;
}}

.pv-stage-desc {{
    font-size: 0.85rem;
    color: var(--pv-text-muted);
    margin: 0.4rem 0;
}}

div[data-testid="stMetricValue"] {{
    font-size: 1.6rem;
    font-weight: 700;
    color: #0F172A;
}}

div[data-testid="stMetricLabel"] {{
    font-size: 0.75rem;
    color: var(--pv-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
}}

button[kind="primary"] {{
    background: var(--pv-primary) !important;
    border-color: var(--pv-primary) !important;
    box-shadow: none !important;
    font-weight: 500;
}}

button[kind="primary"]:hover {{
    background: #4338CA !important;
    border-color: #4338CA !important;
}}

div[data-baseweb="tab-list"] {{
    gap: 1.25rem;
    border-bottom: 1px solid var(--pv-border);
    padding: 0 0.25rem;
    margin-bottom: 0.5rem;
}}

div[data-baseweb="tab"] {{
    font-weight: 500;
    color: var(--pv-text-muted);
    padding: 0.6rem 0.9rem !important;
}}

div[data-baseweb="tab"][aria-selected="true"] {{
    color: var(--pv-primary);
}}

div[data-baseweb="tab-panel"] {{
    padding: 1.5rem 1.25rem 1.75rem 1.25rem !important;
}}

div[data-baseweb="tab-panel"] [data-testid="stDataFrame"],
div[data-baseweb="tab-panel"] [data-testid="stDataFrameContainer"] {{
    margin-top: 0.5rem;
    margin-bottom: 0.75rem;
}}

[data-testid="stDataFrame"],
[data-testid="stDataFrameContainer"] {{
    width: 100% !important;
}}

hr {{
    border: none;
    border-top: 1px solid var(--pv-border);
    margin: 1.5rem 0;
}}

.pv-divider {{
    height: 1px;
    background: var(--pv-border);
    margin: 1.5rem 0;
}}

code {{
    background: #F1F5F9;
    color: #1E293B;
    padding: 0.1rem 0.35rem;
    border-radius: 4px;
    font-size: 0.85em;
}}
</style>
"""


@dataclass
class StageStatus:
    number: int
    name: str
    description: str
    state: str
    state_label: str


def inject_global_styles() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def render_page_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div>
            <p class="pv-eyebrow">{eyebrow}</p>
            <h1 class="pv-page-title">{title}</h1>
            {f'<p class="pv-page-subtitle">{subtitle}</p>' if subtitle else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(label: str, kind: str = "neutral") -> str:
    return f'<span class="pv-badge pv-badge-{kind}">{label}</span>'


def render_sidebar(active: str) -> None:
    with st.sidebar:
        st.markdown(
            """
            <div style="padding: 0.5rem 0 1rem 0;">
                <p class="pv-brand" style="font-size: 1.4rem;">PARIVARTANA</p>
                <p class="pv-tagline">COBOL to Python</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(f"**{active}**")
        st.divider()


def render_stage_status(stages: list[StageStatus]) -> None:
    cols = st.columns(len(stages))
    state_to_kind = {
        "production": "success",
        "in_progress": "warning",
        "beta": "warning",
        "planned": "neutral",
    }
    state_labels = {
        "production": "Live",
        "in_progress": "In Progress",
        "beta": "Beta",
        "planned": "Planned",
    }
    for col, stage in zip(cols, stages):
        with col:
            kind = state_to_kind.get(stage.state, "neutral")
            label = state_labels.get(stage.state, stage.state_label)
            st.markdown(
                f"""
                <div class="pv-stage">
                    <div class="pv-stage-num">STAGE {stage.number:02d}</div>
                    <div class="pv-stage-name">{stage.name}</div>
                    <div>{badge(label, kind)}</div>
                    <p class="pv-stage-desc">{stage.description}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


def empty_state(
    title: str,
    description: str,
    action_label: str | None = None,
    action_target: str | None = None,
) -> None:
    cta_html = ""
    if action_label and action_target:
        cta_html = (
            f'<p style="margin-top: 1rem;">'
            f'<a href="{action_target}" target="_self" '
            f'style="background: {PRIMARY}; color: white; padding: 0.5rem 1rem; '
            f'border-radius: 6px; text-decoration: none; font-weight: 500; font-size: 0.9rem;">'
            f"{action_label}</a></p>"
        )
    st.markdown(
        f"""
        <div class="pv-card" style="text-align: center; padding: 2.5rem 1.5rem; border-style: dashed;">
            <h3 style="margin: 0 0 0.5rem 0; color: #0F172A; font-weight: 600;">{title}</h3>
            <p style="color: var(--pv-text-muted); margin: 0;">{description}</p>
            {cta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
