"""Dashboard Interativo PNCP Intelligence (Streamlit).

Interface visual completa para análise de editais e demandas públicas,
radar de oportunidades imediatas, inteligência temática e exportação de dados.
"""

import html
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Garante acesso aos módulos na raiz do projeto (pncp_intelligence, core)
root_dir = str(Path(__file__).resolve().parents[2])
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pncp_intelligence.src.analytics import PNCPAnalytics
from pncp_intelligence.src.collector import PNCPCollector
from pncp_intelligence.src.db import PNCPDatabase
from pncp_intelligence.src.exporter import PNCPExporter
from pncp_intelligence.src.nlp_analytics import NLPAnalytics
from pncp_intelligence.src.geo_map import GeoMapBuilder, BASES_ESTRATEGICAS, CAPITAIS_INFO
from pncp_intelligence.src.observability import evaluate_health, lineage_for_edital, LINEAGE_STAGES, INDICATOR_LINEAGE
from pncp_intelligence.dashboard.icaro_view import render_icaro_module
from pncp_intelligence.src.formatters import (
    formatar_inteiro,
    formatar_moeda,
    formatar_moeda_compacta,
    formatar_moeda_completa,
    formatar_percentual,
)

# Configuração da página
st.set_page_config(
    page_title="Radar PNCP | Inteligência de Compras Públicas",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================================================
# SELETORES DE TEMA & LAYOUT POWER BI (Inspirado no Power BI Layout Generator)
# ==============================================================
# Seletor de Tema Light/Dark (conforme o switch superior direito da referência)
st.sidebar.markdown("""
<div style="font-size: 11px; font-weight: 700; color: #64748B; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 6px;">
    🎨 Estilo do Dashboard (Power BI)
</div>
""", unsafe_allow_html=True)

col_pbi_th1, col_pbi_th2 = st.sidebar.columns([1, 1])
with col_pbi_th1:
    theme_choice = st.radio("Tema:", ["🌙 Dark", "☀️ Light"], index=0, label_visibility="collapsed", horizontal=True)
with col_pbi_th2:
    layout_style = st.selectbox(
        "Layout Preset:",
        ["03 Top Tabs + 05 Filter", "04 Folder Tabs", "01 Sidebar Clássico"],
        index=0,
        label_visibility="collapsed"
    )

is_dark = (theme_choice == "🌙 Dark")

# Paleta Dinâmica Power BI
c_bg_app = "#0B0F19" if is_dark else "#F8FAFC"
c_bg_grad1 = "rgba(30, 58, 138, 0.18)" if is_dark else "rgba(224, 231, 255, 0.45)"
c_bg_grad2 = "rgba(15, 23, 42, 0.4)" if is_dark else "rgba(241, 245, 249, 0.8)"
c_card_bg = "linear-gradient(180deg, #151C2C 0%, #0F1422 100%)" if is_dark else "#FFFFFF"
c_card_border = "1px solid rgba(255, 255, 255, 0.08)" if is_dark else "1px solid rgba(0, 0, 0, 0.08)"
c_card_hover = "rgba(255, 255, 255, 0.18)" if is_dark else "rgba(37, 99, 235, 0.25)"
c_card_shadow = "0 4px 18px rgba(0, 0, 0, 0.25)" if is_dark else "0 4px 14px rgba(0, 0, 0, 0.06)"
c_text_primary = "#F8FAFC" if is_dark else "#0F172A"
c_text_secondary = "#94A3B8" if is_dark else "#475569"
c_text_muted = "#64748B" if is_dark else "#94A3B8"
c_sidebar_bg = "#0A0E1A" if is_dark else "#F1F5F9"
c_tablist_bg = "#0E131F" if is_dark else "#E2E8F0"
c_banner_bg = "linear-gradient(135deg, #131B2E 0%, #0D1322 100%)" if is_dark else "linear-gradient(135deg, #FFFFFF 0%, #F1F5F9 100%)"
c_banner_border = "rgba(255, 255, 255, 0.09)" if is_dark else "rgba(0, 0, 0, 0.08)"
c_input_bg = "#111624" if is_dark else "#FFFFFF"
c_input_border = "rgba(255, 255, 255, 0.1)" if is_dark else "rgba(0, 0, 0, 0.12)"
c_plotly_bg = "#111624" if is_dark else "#FFFFFF"

# Injeção CSS Dinâmica
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }}

    /* Fundo da Aplicação */
    .stApp {{
        background: {c_bg_app} !important;
        background-image: 
            radial-gradient(at 0% 0%, {c_bg_grad1} 0px, transparent 50%),
            radial-gradient(at 100% 0%, {c_bg_grad2} 0px, transparent 50%) !important;
    }}

    /* Títulos Executivos e Hierarquia Tipográfica Legível */
    h1 {{
        color: {c_text_primary} !important;
        font-size: 28px !important;
        font-weight: 800 !important;
        letter-spacing: -0.02em !important;
        line-height: 1.25 !important;
        margin-bottom: 14px !important;
    }}
    h2 {{
        color: {c_text_primary} !important;
        font-size: 24px !important;
        font-weight: 800 !important;
        letter-spacing: -0.015em !important;
        line-height: 1.3 !important;
        margin-top: 20px !important;
        margin-bottom: 12px !important;
    }}
    h3 {{
        color: {c_text_primary} !important;
        font-size: 21px !important;
        font-weight: 750 !important;
        letter-spacing: -0.01em !important;
        margin-top: 18px !important;
        margin-bottom: 12px !important;
    }}
    h4 {{
        color: {c_text_primary} !important;
        font-size: 18px !important;
        font-weight: 700 !important;
        margin-top: 18px !important;
        margin-bottom: 12px !important;
        border-left: 4px solid #3B82F6;
        padding-left: 12px;
    }}
    h5 {{
        color: {c_text_primary} !important;
        font-size: 16px !important;
        font-weight: 700 !important;
        margin-top: 12px !important;
        margin-bottom: 8px !important;
    }}
    p, span, label, div {{
        font-size: 14.5px;
        line-height: 1.6;
    }}

    /* Banner Superior Executivo */
    .pbi-top-banner {{
        background: {c_banner_bg};
        border: 1px solid {c_banner_border};
        border-radius: 14px;
        padding: 22px 28px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 22px;
        box-shadow: {c_card_shadow};
    }}
    .pbi-banner-left {{
        display: flex;
        align-items: center;
        gap: 18px;
    }}
    .pbi-banner-icon {{
        font-size: 28px;
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.3) 0%, rgba(30, 58, 138, 0.5) 100%);
        border: 1px solid rgba(59, 130, 246, 0.5);
        border-radius: 14px;
        width: 56px;
        height: 56px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.25);
    }}
    .pbi-banner-title {{
        font-size: 24px;
        font-weight: 850;
        color: {c_text_primary};
        letter-spacing: -0.02em;
        line-height: 1.2;
    }}
    .pbi-banner-subtitle {{
        font-size: 13.5px;
        color: {c_text_secondary};
        margin-top: 4px;
        font-weight: 500;
    }}
    .pbi-banner-right {{
        display: flex;
        gap: 12px;
        align-items: center;
    }}
    .pbi-badge {{
        background: {'rgba(255, 255, 255, 0.05)' if is_dark else 'rgba(0, 0, 0, 0.05)'};
        border: 1px solid {'rgba(255, 255, 255, 0.12)' if is_dark else 'rgba(0, 0, 0, 0.1)'};
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 12.5px;
        font-weight: 750;
        color: {c_text_secondary};
        letter-spacing: 0.03em;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    .pbi-badge.active {{
        background: rgba(16, 185, 129, 0.15);
        border-color: rgba(16, 185, 129, 0.45);
        color: #10B981;
    }}
    .pulse-dot {{
        width: 8px;
        height: 8px;
        background-color: #10B981;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 10px #10B981;
        animation: pbiPulse 2s infinite;
    }}
    @keyframes pbiPulse {{
        0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
        70% {{ transform: scale(1); box-shadow: 0 0 0 7px rgba(16, 185, 129, 0); }}
        100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
    }}

    /* Cartões de KPI Executivos */
    .pbi-kpi-card {{
        background: {c_card_bg};
        border: {c_card_border};
        border-radius: 14px;
        padding: 18px 22px;
        box-shadow: {c_card_shadow};
        transition: all 0.25s ease;
        min-height: 120px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        margin-bottom: 20px;
    }}
    .pbi-kpi-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.35);
        border-color: {c_card_hover};
    }}
    .pbi-kpi-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }}
    .pbi-kpi-title {{
        font-size: 12.5px;
        font-weight: 750;
        letter-spacing: 0.05em;
        color: {c_text_secondary};
        text-transform: uppercase;
    }}
    .pbi-kpi-icon {{
        font-size: 16px;
        opacity: 0.95;
    }}
    .pbi-kpi-value {{
        font-size: 32px;
        font-weight: 850;
        color: {c_text_primary};
        line-height: 1.15;
        letter-spacing: -0.02em;
        margin-bottom: 4px;
    }}
    .pbi-kpi-sub {{
        font-size: 12.5px;
        color: {c_text_muted};
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        font-weight: 550;
    }}

    /* Estilização universal para st.metric */
    div[data-testid="stMetric"] {{
        background: {c_card_bg} !important;
        border: {c_card_border} !important;
        border-radius: 12px !important;
        padding: 16px 20px !important;
        box-shadow: {c_card_shadow} !important;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }}
    div[data-testid="stMetric"]:hover {{
        transform: translateY(-2px);
        border-color: rgba(59, 130, 246, 0.5) !important;
    }}
    div[data-testid="stMetric"] label {{
        font-size: 13px !important;
        font-weight: 750 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        color: {c_text_secondary} !important;
    }}
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
        font-size: 30px !important;
        font-weight: 850 !important;
        color: {c_text_primary} !important;
        letter-spacing: -0.02em !important;
    }}
    div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {{
        font-size: 13px !important;
        font-weight: 600 !important;
    }}

    /* Menu Executivo de Navegação na Barra Lateral (Sidebar Radio) */
    div[data-testid="stSidebar"] div[role="radiogroup"] {{
        gap: 6px !important;
        display: flex !important;
        flex-direction: column !important;
    }}
    div[data-testid="stSidebar"] div[role="radiogroup"] > label {{
        background: {'rgba(255, 255, 255, 0.03)' if is_dark else 'rgba(0, 0, 0, 0.03)'} !important;
        border: 1px solid {'rgba(255, 255, 255, 0.07)' if is_dark else 'rgba(0, 0, 0, 0.08)'} !important;
        border-radius: 10px !important;
        padding: 9px 13px !important;
        margin: 0 !important;
        font-size: 13.5px !important;
        font-weight: 600 !important;
        color: {c_text_primary} !important;
        cursor: pointer !important;
        transition: all 0.2s ease !important;
    }}
    div[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{
        background: {'rgba(59, 130, 246, 0.14)' if is_dark else 'rgba(37, 99, 235, 0.08)'} !important;
        border-color: #3B82F6 !important;
        color: #3B82F6 !important;
        transform: translateX(3px) !important;
    }}
    div[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {{
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.28) 0%, rgba(30, 58, 138, 0.4) 100%) !important;
        border: 1.5px solid #3B82F6 !important;
        color: #60A5FA !important;
        font-weight: 750 !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.25) !important;
    }}
        padding: 0 16px !important;
        font-weight: 600 !important;
        font-size: 13px !important;
        color: {c_text_secondary} !important;
        background-color: transparent !important;
        border: none !important;
        transition: all 0.2s ease !important;
    }}
    div[data-baseweb="tab"]:hover {{
        background-color: {'rgba(255, 255, 255, 0.06)' if is_dark else 'rgba(0, 0, 0, 0.04)'} !important;
        color: {c_text_primary} !important;
    }}
    div[data-baseweb="tab"][aria-selected="true"] {{
        background: linear-gradient(135deg, #1E40AF 0%, #2563EB 100%) !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4) !important;
    }}
    div[data-baseweb="tab-highlight"],
    div[data-baseweb="tab-border"] {{
        display: none !important;
    }}

    /* Barra Lateral estilo Power BI Filter Panel (Layout 05) */
    section[data-testid="stSidebar"] {{
        background-color: {c_sidebar_bg} !important;
        border-right: {c_card_border} !important;
    }}
    .sidebar-header-card {{
        background: {'linear-gradient(135deg, #1E293B 0%, #0F172A 100%)' if is_dark else 'linear-gradient(135deg, #FFFFFF 0%, #E2E8F0 100%)'};
        border: {c_card_border};
        border-radius: 10px;
        padding: 14px;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .sidebar-header-title {{
        font-size: 14px;
        font-weight: 700;
        color: {c_text_primary};
        line-height: 1.2;
    }}
    .sidebar-header-sub {{
        font-size: 11px;
        color: {c_text_secondary};
    }}
    .pbi-filter-status {{
        background: {'rgba(59, 130, 246, 0.1)' if is_dark else 'rgba(37, 99, 235, 0.08)'};
        border: 1px solid {'rgba(59, 130, 246, 0.25)' if is_dark else 'rgba(37, 99, 235, 0.2)'};
        border-radius: 8px;
        padding: 10px 12px;
        margin-bottom: 14px;
        font-size: 11.5px;
        color: {c_text_primary};
    }}
    .pbi-progress-bar {{
        background: {'rgba(255, 255, 255, 0.1)' if is_dark else 'rgba(0, 0, 0, 0.08)'};
        height: 4px;
        border-radius: 2px;
        margin-top: 6px;
        overflow: hidden;
    }}
    .pbi-progress-fill {{
        height: 100%;
        background: #3B82F6;
        border-radius: 2px;
    }}

    /* Inputs e Selects na Sidebar */
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div {{
        background-color: {c_input_bg} !important;
        border: 1px solid {c_input_border} !important;
        border-radius: 8px !important;
    }}
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div:hover {{
        border-color: #3B82F6 !important;
    }}
    section[data-testid="stSidebar"] div[data-baseweb="input"] > div {{
        background-color: {c_input_bg} !important;
        border: 1px solid {c_input_border} !important;
        border-radius: 8px !important;
    }}
    div[data-baseweb="tag"] {{
        background: rgba(59, 130, 246, 0.2) !important;
        border: 1px solid rgba(59, 130, 246, 0.4) !important;
        border-radius: 6px !important;
        color: {'#93C5FD' if is_dark else '#1D4ED8'} !important;
        font-weight: 500 !important;
    }}

    /* Botões Primários e Secundários */
    div[data-testid="stButton"] button[kind="primary"] {{
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        border: none !important;
        border-radius: 8px !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35) !important;
        transition: all 0.2s ease !important;
    }}
    div[data-testid="stButton"] button[kind="primary"]:hover {{
        background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 18px rgba(37, 99, 235, 0.5) !important;
    }}
    div[data-testid="stButton"] button[kind="secondary"] {{
        background: {c_card_bg} !important;
        border: {c_card_border} !important;
        border-radius: 8px !important;
        color: {c_text_primary} !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }}
    div[data-testid="stButton"] button[kind="secondary"]:hover {{
        border-color: #3B82F6 !important;
        transform: translateY(-1px) !important;
    }}
    div[data-testid="stDownloadButton"] button {{
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
        border: none !important;
        border-radius: 8px !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 14px rgba(16, 185, 129, 0.3) !important;
        transition: all 0.2s ease !important;
    }}
    div[data-testid="stDownloadButton"] button:hover {{
        background: linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
        transform: translateY(-1px) !important;
    }}

    /* Gráficos Plotly */
    .stPlotlyChart {{
        background: {c_plotly_bg} !important;
        border: {c_card_border} !important;
        border-radius: 12px !important;
        padding: 10px 12px 4px 12px !important;
        box-shadow: {c_card_shadow} !important;
        margin-bottom: 14px !important;
        transition: border-color 0.2s ease;
    }}
    .stPlotlyChart:hover {{
        border-color: {c_card_hover} !important;
    }}

    /* Dataframes */
    div[data-testid="stDataFrame"] {{
        border: {c_card_border} !important;
        border-radius: 10px !important;
        overflow: hidden !important;
    }}
    div[data-testid="stExpander"] {{
        background: {c_card_bg} !important;
        border: {c_card_border} !important;
        border-radius: 10px !important;
    }}

    /* Estilos do Radar Widescreen 3-Fluxos & Gavetas Laterais */
    .radar-stat-box {{
        background: {c_card_bg};
        border: {c_card_border};
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: {c_card_shadow};
        transition: transform 0.2s ease;
    }}
    .radar-stat-box:hover {{
        transform: translateY(-2px);
    }}
    .candidacy-card-item {{
        background: {c_card_bg};
        border: {c_card_border};
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 12px;
        box-shadow: {c_card_shadow};
        border-left: 4px solid #3B82F6;
        transition: all 0.2s ease;
    }}
    .candidacy-card-item:hover {{
        border-color: rgba(59, 130, 246, 0.8);
        box-shadow: 0 6px 20px rgba(0,0,0,0.3);
    }}
    .pillar-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 10.5px;
        color: {c_text_secondary};
        margin-top: 4px;
    }}
    .pillar-bar-bg {{
        flex-grow: 1;
        height: 6px;
        background: {'rgba(255,255,255,0.08)' if is_dark else 'rgba(0,0,0,0.08)'};
        border-radius: 3px;
        margin: 0 8px;
        overflow: hidden;
    }}
    .pillar-bar-fill {{
        height: 100%;
        border-radius: 3px;
    }}
    .drawer-card {{
        background: {c_card_bg};
        border: {c_card_border};
        border-radius: 12px;
        padding: 16px 18px;
        box-shadow: {c_card_shadow};
        margin-bottom: 14px;
    }}
</style>
""", unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def get_services(_version="2026.10.14_v3"):
    db = PNCPDatabase()
    analytics = PNCPAnalytics(db)
    exporter = PNCPExporter(analytics)
    collector = PNCPCollector(db)
    nlp = NLPAnalytics()
    return db, analytics, exporter, collector, nlp


db, analytics, exporter, collector, nlp = get_services(_version="2026.10.14_v3")


def apply_pbi_theme(fig, height=360, is_dark=True):
    """Aplica o tema executivo Power BI aos gráficos Plotly com proporcionalidade e sem sobreposição."""
    font_color = "#CBD5E1" if is_dark else "#334155"
    grid_color = "rgba(255, 255, 255, 0.05)" if is_dark else "rgba(0, 0, 0, 0.06)"
    line_color = "rgba(255, 255, 255, 0.12)" if is_dark else "rgba(0, 0, 0, 0.12)"
    legend_bg = "rgba(15, 23, 42, 0.85)" if is_dark else "rgba(255, 255, 255, 0.92)"
    legend_border = "rgba(255, 255, 255, 0.1)" if is_dark else "rgba(0, 0, 0, 0.1)"

    has_title = bool(fig.layout.title and fig.layout.title.text)
    top_margin = 56 if has_title else 22
    bottom_margin = 48 if (fig.layout.showlegend is not False and len(fig.data) > 1) else 24

    try:
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Plus Jakarta Sans, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif", color=font_color, size=12),
            margin=dict(l=35, r=25, t=top_margin, b=bottom_margin),
            height=height,
            xaxis=dict(
                gridcolor=grid_color,
                linecolor=line_color,
                tickfont=dict(color=font_color, size=11),
                title=dict(font=dict(color=font_color, size=12)),
                automargin=True
            ),
            yaxis=dict(
                gridcolor=grid_color,
                linecolor=line_color,
                tickfont=dict(color=font_color, size=11),
                title=dict(font=dict(color=font_color, size=12)),
                automargin=True
            ),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.14,
                xanchor="center",
                x=0.5,
                bgcolor=legend_bg,
                bordercolor=legend_border,
                borderwidth=1,
                font=dict(color=font_color, size=11)
            )
        )
        if has_title:
            fig.update_layout(
                title=dict(
                    y=0.96,
                    x=0.01,
                    xanchor="left",
                    yanchor="top",
                    font=dict(color=font_color, size=13)
                )
            )
    except Exception:
        # Fallback para gráficos sem eixos cartesianos (ex: Treemaps)
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Plus Jakarta Sans, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif", color=font_color, size=12),
            margin=dict(l=25, r=25, t=top_margin, b=bottom_margin),
            height=height,
        )
    return fig


def build_sankey_ramificacoes(df, is_dark=True, return_metadata=False):
    """Constrói o diagrama de ramificações Sankey / Alluvial com detalhamento por Vertical e Subtema especializado.

    Fluxo em 4 Estágios com destaque e amplo espaçamento na parte direita:
    Modalidade (x=0.01) ➔ Vertical Estratégica (x=0.20) ➔ Subtema Especializado (x=0.62) ➔ Decisão Tática (x=0.99).
    """
    if df.empty:
        empty_fig = go.Figure()
        return (empty_fig, []) if return_metadata else empty_fig

    # Filtra apenas registros com categorização válida
    df_flow = df[df["matched_category"].notna() & (df["matched_category"].astype(str).str.strip() != "")].copy()
    if df_flow.empty:
        empty_fig = go.Figure()
        return (empty_fig, []) if return_metadata else empty_fig

    df_flow["modalidade_curta"] = df_flow["modalidade_nome"].fillna("Outra").apply(
        lambda m: "Pregão Eletrônico" if "pregão" in str(m).lower()
        else ("Dispensa" if "dispensa" in str(m).lower()
        else ("Credenciamento" if "credenciamento" in str(m).lower()
        else ("Concorrência" if "concorrência" in str(m).lower() else "Outras Modalidades")))
    )
    df_flow["categoria_label"] = df_flow["matched_category"].fillna("Políticas Públicas & Dados")
    df_flow["subtema_label"] = df_flow["matched_subtema"].fillna("Geral")

    if "decisao_tag" in df_flow.columns:
        df_flow["decisao"] = df_flow["decisao_tag"].fillna("🟡 WATCH")
    else:
        def _quick_decisao(row):
            sub = str(row.get("matched_subtema", "")).lower()
            mod = str(row.get("modalidade_nome", "")).lower()
            val = float(row.get("valor_total_estimado", 0) or 0)
            if "dispensa" in mod or any(k in sub for k in ["dados", "ia", "intelligence", "dashboards", "steam", "computacional", "ideb", "vaar", "lgpd", "machine learning"]):
                return "🟢 GO" if (val >= 50000 or val == 0) else "🟡 WATCH"
            elif any(k in sub for k in ["consultoria", "governança", "projetos", "educacional", "planejamento", "transformacao"]):
                return "🟡 WATCH"
            return "🔴 NO-GO"
        df_flow["decisao"] = df_flow.apply(_quick_decisao, axis=1)

    if "dias_restantes" not in df_flow.columns:
        df_flow["dias_restantes"] = 0.0

    mods = sorted(df_flow["modalidade_curta"].unique().tolist())
    cats = sorted(df_flow["categoria_label"].unique().tolist())
    subs = sorted(df_flow["subtema_label"].unique().tolist())
    decs = [d for d in ["🟢 GO", "🟡 WATCH", "🔴 NO-GO"] if d in df_flow["decisao"].unique()]
    if not decs:
        decs = sorted(df_flow["decisao"].unique().tolist())

    # Prefixos para evitar colisão de nomes caso um nó tenha o mesmo rótulo
    all_node_keys = [f"MOD::{m}" for m in mods] + [f"CAT::{c}" for c in cats] + [f"SUB::{s}" for s in subs] + [f"DEC::{d}" for d in decs]
    node_map = {k: idx for idx, k in enumerate(all_node_keys)}

    color_map = {
        "🟢 GO": "#10B981",
        "🟡 WATCH": "#F59E0B",
        "🔴 NO-GO": "#EF4444",
        "Pregão Eletrônico": "#3B82F6",
        "Dispensa": "#10B981",
        "Credenciamento": "#8B5CF6",
        "Concorrência": "#EC4899",
        "Outras Modalidades": "#64748B",
        # Verticais
        "Dados, IA & Políticas Públicas": "#06B6D4",
        "Governança & Gestão de Projetos Estratégicos": "#6366F1",
        "Políticas Educacionais & STEAM": "#F59E0B",
        # Subtemas Dados & IA
        "Inteligência Artificial & Machine Learning": "#8B5CF6",
        "Business Intelligence & Dashboards": "#0284C7",
        "Engenharia de Dados & Infraestrutura Cloud": "#0EA5E9",
        "Ciência de Dados & Analytics": "#38BDF8",
        "Monitoramento & Avaliação (M&A / MEL)": "#0D9488",
        # Subtemas Governança & Projetos
        "Privacidade & Proteção de Dados (LGPD)": "#EC4899",
        "Governança Pública & Planejamento": "#6366F1",
        "Consultoria & Assessoria Técnica Especializada": "#7C3AED",
        "Gestão de Projetos & Processos (PMO / BPM)": "#4F46E5",
        "Transformação & Governo Digital": "#14B8A6",
        # Subtemas Educação
        "Pensamento Computacional & STEAM": "#F43F5E",
        "Avaliação Educacional, IDEB & VAAR": "#10B981",
        "Tecnologias & Inovação Educacional": "#D97706",
        "Políticas Educacionais & Educação Básica": "#B45309"
    }

    sub_icons = {
        "Inteligência Artificial & Machine Learning": "🤖",
        "Privacidade & Proteção de Dados (LGPD)": "🔒",
        "Governança Pública & Planejamento": "🏛️",
        "Consultoria & Assessoria Técnica Especializada": "📑",
        "Avaliação Educacional, IDEB & VAAR": "🟢",
        "Business Intelligence & Dashboards": "📊",
        "Pensamento Computacional & STEAM": "🌸",
        "Engenharia de Dados & Infraestrutura Cloud": "🗄️",
        "Políticas Educacionais & Educação Básica": "🟤",
        "Tecnologias & Inovação Educacional": "📙",
        "Gestão de Projetos & Processos (PMO / BPM)": "⚡",
        "Monitoramento & Avaliação (M&A / MEL)": "🎯",
        "Transformação & Governo Digital": "🌐",
        "Ciência de Dados & Analytics": "🔬",
    }

    node_colors = [color_map.get(k.split("::", 1)[1], "#38BDF8") for k in all_node_keys]

    # Posicionamento horizontal das 4 colunas dando amplo destaque e respiro à direita
    node_x = []
    display_labels = []
    for k in all_node_keys:
        lbl_orig = k.split("::", 1)[1]
        if k.startswith("MOD::"):
            cnt = len(df_flow[df_flow["modalidade_curta"] == lbl_orig])
            display_labels.append(f"{lbl_orig} ({cnt})")
            node_x.append(0.01)
        elif k.startswith("CAT::"):
            cnt = len(df_flow[df_flow["categoria_label"] == lbl_orig])
            display_labels.append(f"{lbl_orig} ({cnt})")
            node_x.append(0.20)
        elif k.startswith("SUB::"):
            cnt = len(df_flow[df_flow["subtema_label"] == lbl_orig])
            icon = sub_icons.get(lbl_orig, "📁")
            display_labels.append(f"{icon} {lbl_orig} ({cnt})")
            node_x.append(0.62)
        else:
            cnt = len(df_flow[df_flow["decisao"] == lbl_orig])
            display_labels.append(f"{lbl_orig} ({cnt})")
            node_x.append(0.99)

    # Estatísticas consolidadas e listas de editais para cada nó
    tot_pipe = max(1.0, float(df_flow["valor_total_estimado"].sum()))
    node_customdata = []
    node_editais_json = []

    for k in all_node_keys:
        lbl_orig = k.split("::", 1)[1]
        if k.startswith("MOD::"):
            sub_df = df_flow[df_flow["modalidade_curta"] == lbl_orig]
        elif k.startswith("CAT::"):
            sub_df = df_flow[df_flow["categoria_label"] == lbl_orig]
        elif k.startswith("SUB::"):
            sub_df = df_flow[df_flow["subtema_label"] == lbl_orig]
        else:
            sub_df = df_flow[df_flow["decisao"] == lbl_orig]

        v_n = float(sub_df["valor_total_estimado"].sum())
        q_n = len(sub_df)
        pct_n = (v_n / tot_pipe) * 100
        tm_n = v_n / max(1, q_n)

        sub_sort_cols = [c for c in ["score_candidatura", "valor_total_estimado"] if c in sub_df.columns]
        sub_sorted = sub_df.sort_values(by=sub_sort_cols, ascending=False) if sub_sort_cols else sub_df.copy()

        tooltip_items = []
        ed_json_list = []

        for _, ed in sub_sorted.iterrows():
            org = str(ed.get("razao_social_orgao", "Órgão"))
            uf = str(ed.get("uf_sigla", ""))
            val_raw = float(ed.get("valor_total_estimado", 0) or 0)
            val_fmt = formatar_moeda_compacta(val_raw)
            sc_val = ed.get("score_candidatura", 0)
            try:
                sc = int(float(sc_val)) if pd.notna(sc_val) else 0
            except Exception:
                sc = 0
            dias = float(ed.get("dias_restantes", 0.0) or 0.0)
            prazo_str = f"{dias:.1f}d" if dias > 0 else "Encerrado"
            pncp_id = str(ed.get("numero_controle_pncp", ""))
            url = ed.get("url_oficial_edital") or f"https://pncp.gov.br/app/editais/{pncp_id}"
            mod = str(ed.get("modalidade_nome", ""))
            obj = str(ed.get("objeto_compra", ""))
            dec = str(ed.get("decisao_tag", "WATCH"))

            ed_json_list.append({
                "orgao": org,
                "uf": uf,
                "valor": val_fmt,
                "score": sc,
                "prazo": prazo_str,
                "pncp_id": pncp_id,
                "url": url,
                "modalidade": mod,
                "objeto": (obj[:140] + ("..." if len(obj) > 140 else "")) if obj else "Sem descrição detalhada",
                "decisao": dec
            })

        for ed in ed_json_list[:4]:
            tooltip_items.append(f"• <b>{ed['orgao'][:26]} ({ed['uf']})</b>: {ed['valor']} (Fit {ed['score']} pts)")

        if q_n > 4:
            tooltip_items.append(f"<i>... e mais {q_n - 4} editais</i>")

        tooltip_links_str = "<br>".join(tooltip_items) if tooltip_items else "<i>Nenhum edital ativo</i>"

        node_customdata.append([
            formatar_moeda_compacta(v_n),
            f"{pct_n:.1f}",
            formatar_moeda_compacta(tm_n),
            q_n,
            tooltip_links_str
        ])

        node_editais_json.append({
            "label": lbl_orig,
            "key": k,
            "total_editais": q_n,
            "volume_fmt": formatar_moeda_compacta(v_n),
            "ticket_medio": formatar_moeda_compacta(tm_n),
            "editais": ed_json_list[:15]
        })

    sources = []
    targets = []
    values = []
    link_colors = []
    customdata = []

    # Estágio 1: Modalidade -> Vertical Categoria
    flow1 = df_flow.groupby(["modalidade_curta", "categoria_label"]).agg(
        qtd=("id", "count"),
        valor=("valor_total_estimado", "sum"),
        dias_medio=("dias_restantes", "mean")
    ).reset_index()

    for _, r in flow1.iterrows():
        sources.append(node_map[f"MOD::{r['modalidade_curta']}"])
        targets.append(node_map[f"CAT::{r['categoria_label']}"])
        values.append(int(r["qtd"]))
        link_colors.append("rgba(56, 189, 248, 0.28)" if is_dark else "rgba(56, 189, 248, 0.38)")
        tm = r["valor"] / max(1, r["qtd"])
        customdata.append([
            formatar_moeda_compacta(r["valor"]),
            formatar_moeda_compacta(tm),
            "Vertical de Atuação",
            f"{r['dias_medio']:.1f}d",
            ""
        ])

    # Estágio 2: Vertical Categoria -> Subtema Especializado
    flow2 = df_flow.groupby(["categoria_label", "subtema_label"]).agg(
        qtd=("id", "count"),
        valor=("valor_total_estimado", "sum"),
        dias_medio=("dias_restantes", "mean")
    ).reset_index()

    for _, r in flow2.iterrows():
        sources.append(node_map[f"CAT::{r['categoria_label']}"])
        targets.append(node_map[f"SUB::{r['subtema_label']}"])
        values.append(int(r["qtd"]))
        link_colors.append("rgba(99, 102, 241, 0.30)" if is_dark else "rgba(99, 102, 241, 0.40)")
        tm = r["valor"] / max(1, r["qtd"])
        customdata.append([
            formatar_moeda_compacta(r["valor"]),
            formatar_moeda_compacta(tm),
            "Especialidade B2G",
            f"{r['dias_medio']:.1f}d",
            ""
        ])

    # Estágio 3: Subtema Especializado -> Decisão Estratégica (com editais e links nos fluxos)
    flow3 = df_flow.groupby(["subtema_label", "decisao"]).agg(
        qtd=("id", "count"),
        valor=("valor_total_estimado", "sum"),
        dias_medio=("dias_restantes", "mean")
    ).reset_index()

    dec_link_colors = {
        "🟢 GO": "rgba(16, 185, 129, 0.45)" if is_dark else "rgba(16, 185, 129, 0.55)",
        "🟡 WATCH": "rgba(245, 158, 11, 0.45)" if is_dark else "rgba(245, 158, 11, 0.55)",
        "🔴 NO-GO": "rgba(239, 68, 68, 0.38)" if is_dark else "rgba(239, 68, 68, 0.45)"
    }

    for _, r in flow3.iterrows():
        sub_ed_link = df_flow[(df_flow["subtema_label"] == r["subtema_label"]) & (df_flow["decisao"] == r["decisao"])]
        link_sort_cols = [c for c in ["score_candidatura", "valor_total_estimado"] if c in sub_ed_link.columns]
        link_sorted = sub_ed_link.sort_values(by=link_sort_cols, ascending=False) if link_sort_cols else sub_ed_link.copy()
        link_items = []
        for _, ed in link_sorted.head(3).iterrows():
            org = str(ed.get("razao_social_orgao", "Órgão"))[:24]
            uf = str(ed.get("uf_sigla", ""))
            val_fmt = formatar_moeda_compacta(float(ed.get("valor_total_estimado", 0) or 0))
            sc_val = ed.get("score_candidatura", 0)
            try:
                sc = int(float(sc_val)) if pd.notna(sc_val) else 0
            except Exception:
                sc = 0
            link_items.append(f"• <b>{org} ({uf})</b>: {val_fmt} (Fit {sc} pts)")
        if len(sub_ed_link) > 3:
            link_items.append(f"<i>... e mais {len(sub_ed_link) - 3} editais</i>")
        link_links_str = "<br>".join(link_items) if link_items else "<i>Sem editais</i>"

        sources.append(node_map[f"SUB::{r['subtema_label']}"])
        targets.append(node_map[f"DEC::{r['decisao']}"])
        values.append(int(r["qtd"]))
        link_colors.append(dec_link_colors.get(r["decisao"], "rgba(148, 163, 184, 0.3)"))
        tm = r["valor"] / max(1, r["qtd"])
        customdata.append([
            formatar_moeda_compacta(r["valor"]),
            formatar_moeda_compacta(tm),
            r["decisao"],
            f"{r['dias_medio']:.1f}d",
            link_links_str
        ])

    calc_height = max(880, len(subs) * 58)

    fig = go.Figure(data=[go.Sankey(
        arrangement="snap",
        node=dict(
            pad=16,
            thickness=24,
            line=dict(color="#0F172A" if is_dark else "#CBD5E1", width=2),
            label=display_labels,
            color=node_colors,
            customdata=node_customdata,
            x=node_x,
            hovertemplate="<b>📌 %{label}</b><br>─────────────────────────────<br>📦 <b>Total:</b> %{customdata[3]} editais • 💰 <b>Volume:</b> %{customdata[0]}<br>🎯 <b>Ticket Médio:</b> %{customdata[2]} • 📊 <b>Fatia do Pipeline:</b> %{customdata[1]}%<br>─────────────────────────────<br>⭐ <b>Principais Oportunidades:</b><br>%{customdata[4]}<extra></extra>"
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            color=link_colors,
            customdata=customdata,
            hovertemplate="<b>🌿 %{source.label} ➔ %{target.label}</b><br>─────────────────────────────<br>📦 <b>Oportunidades:</b> %{value} editais • 💰 <b>Volume Total:</b> %{customdata[0]}<br>🎯 <b>Ticket Médio:</b> %{customdata[1]} • ⚡ <b>Direcionamento:</b> %{customdata[2]} • ⏳ <b>Prazo Médio:</b> %{customdata[3]}<br>─────────────────────────────<br>⭐ <b>Destaques do Fluxo:</b><br>%{customdata[4]}<extra></extra>"
        )
    )])

    fig.update_layout(
        font=dict(family="Plus Jakarta Sans, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif", size=11.5, color="#F1F5F9" if is_dark else "#0F172A"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=calc_height,
        margin=dict(l=15, r=15, t=20, b=20)
    )

    fig._node_editais_json = node_editais_json
    if return_metadata:
        return fig, node_editais_json
    return fig


def render_interactive_sankey_widescreen(df_flow, is_dark=True):
    """Renderiza o Dataviz Widescreen de Ramificações Sankey com painel dinâmico
    que gera a lista de links clicáveis imediatamente ao passar o mouse.
    """
    if df_flow.empty:
        st.info("Nenhum edital atende aos filtros atuais para o diagrama Sankey.")
        return

    fig, node_meta = build_sankey_ramificacoes(df_flow, is_dark=is_dark, return_metadata=True)
    if not fig.data:
        st.info("Nenhum dado categorizado disponível para traçar o fluxo.")
        return

    fig_json = fig.to_json().replace("</script>", "<\\/script>")
    node_meta_json = json.dumps(node_meta).replace("</script>", "<\\/script>")

    # Editais de maior fit para exibição inicial no painel
    top_sort_cols = [c for c in ["score_candidatura", "valor_total_estimado"] if c in df_flow.columns]
    top_default = (df_flow.sort_values(by=top_sort_cols, ascending=False) if top_sort_cols else df_flow).head(10).to_dict(orient="records")
    default_cards = []
    for ed in top_default:
        val_fmt = formatar_moeda_compacta(float(ed.get("valor_total_estimado", 0) or 0))
        sc_val = ed.get("score_candidatura", 0)
        try:
            sc = int(float(sc_val)) if pd.notna(sc_val) else 0
        except Exception:
            sc = 0
        dias = float(ed.get("dias_restantes", 0.0) or 0.0)
        prazo = f"{dias:.1f}d" if dias > 0 else "Encerrado"
        pncp_id = str(ed.get("numero_controle_pncp", ""))
        url = ed.get("url_oficial_edital") or f"https://pncp.gov.br/app/editais/{pncp_id}"
        obj = str(ed.get("objeto_compra", ""))
        default_cards.append({
            "orgao": str(ed.get("razao_social_orgao", "Órgão")),
            "uf": str(ed.get("uf_sigla", "")),
            "valor": val_fmt,
            "score": sc,
            "prazo": prazo,
            "pncp_id": pncp_id,
            "url": url,
            "modalidade": str(ed.get("modalidade_nome", "")),
            "objeto": (obj[:140] + ("..." if len(obj) > 140 else "")) if obj else "Sem descrição detalhada",
            "decisao": str(ed.get("decisao_tag", "WATCH"))
        })
    default_meta_json = json.dumps(default_cards).replace("</script>", "<\\/script>")

    bg_card = "rgba(15, 23, 42, 0.85)" if is_dark else "rgba(248, 250, 252, 0.95)"
    border_col = "rgba(255, 255, 255, 0.12)" if is_dark else "rgba(0, 0, 0, 0.12)"
    text_primary = "#F8FAFC" if is_dark else "#0F172A"
    text_secondary = "#94A3B8" if is_dark else "#475569"
    card_hover_bg = "rgba(30, 41, 59, 0.95)" if is_dark else "rgba(255, 255, 255, 1.0)"
    card_border = "rgba(56, 189, 248, 0.25)" if is_dark else "rgba(56, 189, 248, 0.35)"
    calc_h = getattr(fig.layout, "height", 900) or 900
    comp_h = int(calc_h) + 40

    html_code = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            padding: 0;
            background: transparent;
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;
            color: {text_primary};
        }}
        .main-container {{
            display: flex;
            gap: 16px;
            width: 100%;
            height: {calc_h}px;
        }}
        .chart-box {{
            flex: 2.2;
            height: 100%;
            background: {bg_card};
            border: 1px solid {border_col};
            border-radius: 12px;
            padding: 8px;
            position: relative;
        }}
        #sankey-div {{
            width: 100%;
            height: 100%;
        }}
        .panel-box {{
            flex: 1.1;
            height: 100%;
            background: {bg_card};
            border: 1.5px solid rgba(56, 189, 248, 0.45);
            border-radius: 12px;
            padding: 14px 16px;
            display: flex;
            flex-direction: column;
            box-shadow: 0 8px 24px rgba(0,0,0,0.3);
        }}
        .panel-header {{
            padding-bottom: 10px;
            border-bottom: 1px solid {border_col};
            margin-bottom: 12px;
        }}
        .panel-title {{
            font-size: 15px;
            font-weight: 800;
            color: #38BDF8;
            margin: 0 0 4px 0;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .panel-subtitle {{
            font-size: 11.5px;
            color: {text_secondary};
            margin: 0;
            line-height: 1.35;
        }}
        .cards-scroll {{
            flex: 1;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 10px;
            padding-right: 6px;
        }}
        .cards-scroll::-webkit-scrollbar {{
            width: 6px;
        }}
        .cards-scroll::-webkit-scrollbar-track {{
            background: rgba(0,0,0,0.1);
            border-radius: 4px;
        }}
        .cards-scroll::-webkit-scrollbar-thumb {{
            background: rgba(56, 189, 248, 0.4);
            border-radius: 4px;
        }}
        .edital-card {{
            background: {card_hover_bg};
            border: 1px solid {card_border};
            border-radius: 10px;
            padding: 12px 14px;
            transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
        }}
        .edital-card:hover {{
            transform: translateY(-2px);
            border-color: #38BDF8;
            box-shadow: 0 4px 14px rgba(56, 189, 248, 0.2);
        }}
        .card-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }}
        .badge-dec {{
            font-size: 10.5px;
            font-weight: 800;
            padding: 2px 7px;
            border-radius: 5px;
        }}
        .badge-go {{ background: rgba(16, 185, 129, 0.18); color: #10B981; border: 1px solid rgba(16, 185, 129, 0.3); }}
        .badge-watch {{ background: rgba(245, 158, 11, 0.18); color: #F59E0B; border: 1px solid rgba(245, 158, 11, 0.3); }}
        .badge-nogo {{ background: rgba(239, 68, 68, 0.18); color: #EF4444; border: 1px solid rgba(239, 68, 68, 0.3); }}
        .badge-score {{
            font-size: 11px;
            font-weight: 800;
            color: #38BDF8;
            background: rgba(56, 189, 248, 0.12);
            padding: 2px 8px;
            border-radius: 6px;
        }}
        .card-orgao {{
            font-size: 13px;
            font-weight: 700;
            color: {text_primary};
            margin-bottom: 4px;
            line-height: 1.3;
        }}
        .card-meta {{
            font-size: 11px;
            color: {text_secondary};
            margin-bottom: 6px;
        }}
        .card-objeto {{
            font-size: 11.5px;
            color: {text_primary};
            background: rgba(255,255,255,0.03);
            border-left: 2px solid #38BDF8;
            padding: 6px 8px;
            border-radius: 4px;
            margin-bottom: 9px;
            line-height: 1.35;
        }}
        .btn-pncp {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            padding: 7px 10px;
            background: #2563EB;
            color: #FFFFFF !important;
            font-size: 11.5px;
            font-weight: 700;
            text-decoration: none;
            border-radius: 6px;
            transition: background 0.2s ease;
        }}
        .btn-pncp:hover {{
            background: #1D4ED8;
        }}
        .reset-btn {{
            font-size: 11px;
            background: transparent;
            border: 1px solid {border_col};
            color: {text_secondary};
            padding: 3px 8px;
            border-radius: 5px;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        .reset-btn:hover {{
            background: rgba(56, 189, 248, 0.15);
            color: #38BDF8;
            border-color: #38BDF8;
        }}
    </style>
</head>
<body>
    <div class="main-container">
        <div class="chart-box">
            <div id="sankey-div"></div>
        </div>
        <div class="panel-box">
            <div class="panel-header">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                    <div id="panel-title" class="panel-title">🎯 Radar de Links Imediatos</div>
                    <button class="reset-btn" onclick="resetToDefault()">↺ Top Fit</button>
                </div>
                <div id="panel-subtitle" class="panel-subtitle">Passe o mouse sobre qualquer ramo ou nó à esquerda para listar os editais e links.</div>
            </div>
            <div id="cards-container" class="cards-scroll"></div>
        </div>
    </div>

    <script>
        const figData = {fig_json};
        const NODES = {node_meta_json};
        const DEFAULT_CARDS = {default_meta_json};

        Plotly.newPlot('sankey-div', figData.data, figData.layout, {{
            responsive: true,
            displayModeBar: false
        }});

        function createCardHtml(e) {{
            let badgeClass = 'badge-watch';
            if (e.decisao.includes('GO') && !e.decisao.includes('NO-GO')) badgeClass = 'badge-go';
            else if (e.decisao.includes('NO-GO')) badgeClass = 'badge-nogo';

            return `
                <div class="edital-card">
                    <div class="card-top">
                        <span class="badge-dec ${{badgeClass}}">${{e.decisao}}</span>
                        <span class="badge-score">Fit: ${{e.score}}/100</span>
                        <span style="font-size: 11px; color: #94A3B8; font-weight: 600;">⏳ ${{e.prazo}}</span>
                    </div>
                    <div class="card-orgao">🏛️ ${{e.orgao}} (${{e.uf}})</div>
                    <div class="card-meta">
                        ${{e.modalidade}} • <b style="color: #38BDF8;">${{e.valor}}</b>
                    </div>
                    <div class="card-objeto">${{e.objeto}}</div>
                    <a href="${{e.url}}" target="_blank" rel="noopener noreferrer" class="btn-pncp">
                        🔗 Abrir no Portal do PNCP ↗
                    </a>
                </div>
            `;
        }}

        function renderCardsList(title, subtitle, editaisList) {{
            document.getElementById('panel-title').innerText = title;
            document.getElementById('panel-subtitle').innerText = subtitle;
            const container = document.getElementById('cards-container');
            if (!editaisList || editaisList.length === 0) {{
                container.innerHTML = '<div style="font-size: 12px; color: #94A3B8; text-align: center; padding: 20px;">Nenhum edital disponível neste ramo.</div>';
                return;
            }}
            container.innerHTML = editaisList.map(createCardHtml).join('');
        }}

        function resetToDefault() {{
            renderCardsList('⭐ Top Editais Recomendados', 'Exibindo oportunidades de maior pontuação do pipeline atual.', DEFAULT_CARDS);
        }}

        resetToDefault();

        const gd = document.getElementById('sankey-div');
        gd.on('plotly_hover', function(data) {{
            if (!data || !data.points || data.points.length === 0) return;
            const pt = data.points[0];
            if (pt.hasOwnProperty('pointNumber') && NODES[pt.pointNumber]) {{
                const node = NODES[pt.pointNumber];
                const title = '📌 ' + node.label;
                const sub = '📦 ' + node.total_editais + ' editais • 💰 ' + node.volume_fmt + ' • 🎯 Médio: ' + node.ticket_medio;
                renderCardsList(title, sub, node.editais);
            }}
        }});
    </script>
</body>
</html>"""
    components.html(html_code, height=comp_h, scrolling=False)


def calcular_risco_retorno(df):
    """Calcula métricas quanti-quali de Risco Operacional vs Potencial de Retorno

    para cada contratação, classificando em 4 Quadrantes Estratégicos.
    """
    if df.empty:
        return df

    import numpy as np
    df_out = df.copy()

    def calc_retorno(row):
        val = float(row.get("valor_total_estimado", 0.0) or 0.0)
        if val <= 50000:
            s_val = 40.0 + (val / 50000.0) * 15.0
        elif val <= 300000:
            s_val = 55.0 + ((val - 50000.0) / 250000.0) * 25.0
        elif val <= 1500000:
            s_val = 80.0 + ((val - 300000.0) / 1200000.0) * 15.0
        else:
            s_val = min(100.0, 95.0 + np.log10(val / 1500000.0 + 1) * 2.5)

        sub = str(row.get("matched_subtema", "")).lower()
        bonus = 0.0
        if any(k in sub for k in ["saas", "software", "nuvem", "cloud"]):
            bonus += 8.0
        elif any(k in sub for k in ["ia", "dados", "business intelligence"]):
            bonus += 10.0
        elif any(k in sub for k in ["educacao", "ideb", "robotica"]):
            bonus += 6.0

        return max(10, min(100, int(round(s_val * 0.9 + bonus))))

    def calc_risco(row):
        mod = str(row.get("modalidade_nome", "")).lower()
        if "dispensa" in mod:
            r_mod = 12.0
        elif "credenciamento" in mod or "inexigibilidade" in mod:
            r_mod = 25.0
        elif "pregão" in mod:
            r_mod = 45.0
        elif "concorrência" in mod:
            r_mod = 82.0
        else:
            r_mod = 60.0

        dias = float(row.get("dias_restantes", 7.0) or 7.0)
        if dias <= 1.5:
            r_prazo = 25.0
        elif dias <= 3.0:
            r_prazo = 15.0
        elif dias <= 7.0:
            r_prazo = 5.0
        else:
            r_prazo = 0.0

        dist = float(row.get("distancia_km", 0.0) or 0.0)
        base = str(row.get("base_logistica", "")).lower()
        if "remoto" in base:
            r_log = 0.0
        elif dist > 500:
            r_log = 18.0
        elif dist > 250:
            r_log = 10.0
        else:
            r_log = 2.0

        return max(5, min(95, int(round(r_mod * 0.7 + r_prazo + r_log))))

    df_out["score_retorno"] = df_out.apply(calc_retorno, axis=1)
    df_out["score_risco"] = df_out.apply(calc_risco, axis=1)

    def classificar_quadrante(row):
        r = row["score_risco"]
        ret = row["score_retorno"]
        if r <= 50 and ret >= 60:
            return "🟢 Joias da Coroa (Alto Retorno / Baixo Risco)"
        elif r <= 50 and ret < 60:
            return "🔵 Fluxo Contínuo (Retorno Médio / Baixo Risco)"
        elif r > 50 and ret >= 60:
            return "🟣 Grandes Apostas (Alto Retorno / Alto Risco)"
        else:
            return "🔴 Armadilhas (Baixo Retorno / Alto Risco)"

    df_out["quadrante_estrategico"] = df_out.apply(classificar_quadrante, axis=1)
    df_out["razao_risco_retorno"] = (df_out["score_retorno"] / df_out["score_risco"].clip(lower=1)).round(2)

    return df_out


def build_risco_retorno_chart(df, is_dark=True):
    """Constrói o gráfico de dispersão em 4 Quadrantes Estratégicos de Risco x Retorno."""
    if df.empty:
        return go.Figure()

    df_p = df.copy()
    df_p["valor_fmt"] = df_p["valor_total_estimado"].apply(formatar_moeda_completa)
    df_p["dias_fmt"] = df_p["dias_restantes"].apply(lambda d: f"{d:.1f}d")
    df_p["orgao_curto"] = df_p["razao_social_orgao"].fillna("Órgão").apply(lambda o: str(o)[:35] + "..." if len(str(o)) > 35 else str(o))

    color_map = {
        "🟢 Joias da Coroa (Alto Retorno / Baixo Risco)": "#10B981",
        "🔵 Fluxo Contínuo (Retorno Médio / Baixo Risco)": "#38BDF8",
        "🟣 Grandes Apostas (Alto Retorno / Alto Risco)": "#A855F7",
        "🔴 Armadilhas (Baixo Retorno / Alto Risco)": "#EF4444"
    }

    fig = go.Figure()

    for quad, cor in color_map.items():
        df_q = df_p[df_p["quadrante_estrategico"] == quad]
        if df_q.empty:
            continue

        fig.add_trace(go.Scatter(
            x=df_q["score_risco"],
            y=df_q["score_retorno"],
            mode="markers",
            name=quad.split(" (")[0],
            marker=dict(
                size=df_q["score_retorno"].apply(lambda s: max(10, min(26, int(s / 4.0)))),
                color=cor,
                opacity=0.88,
                line=dict(width=1.2, color="#FFFFFF" if is_dark else "#0F172A")
            ),
            text=df_q["orgao_curto"],
            customdata=list(zip(
                df_q["quadrante_estrategico"],
                df_q["score_retorno"],
                df_q["score_risco"],
                df_q["razao_risco_retorno"],
                df_q["valor_fmt"],
                df_q["modalidade_nome"],
                df_q["matched_subtema"],
                df_q["dias_fmt"]
            )),
            hovertemplate=(
                "<b>%{text}</b><br><br>"
                "🎯 <b>Classificação:</b> %{customdata[0]}<br>"
                "📈 <b>Retorno:</b> %{customdata[1]}/100 | ⚠️ <b>Risco:</b> %{customdata[2]}/100<br>"
                "⚡ <b>Relação Retorno/Risco:</b> %{customdata[3]}x<br>"
                "💰 <b>Valor Estimado:</b> %{customdata[4]}<br>"
                "🏛️ <b>Modalidade:</b> %{customdata[5]}<br>"
                "📦 <b>Demanda:</b> %{customdata[6]}<br>"
                "⏳ <b>Prazo:</b> %{customdata[7]}<extra></extra>"
            )
        ))

    shapes = [
        dict(type="rect", xref="x", yref="y", x0=0, y0=60, x1=50, y1=100, fillcolor="rgba(16, 185, 129, 0.08)", line_width=0, layer="below"),
        dict(type="rect", xref="x", yref="y", x0=0, y0=0, x1=50, y1=60, fillcolor="rgba(56, 189, 248, 0.06)", line_width=0, layer="below"),
        dict(type="rect", xref="x", yref="y", x0=50, y0=60, x1=100, y1=100, fillcolor="rgba(168, 85, 247, 0.08)", line_width=0, layer="below"),
        dict(type="rect", xref="x", yref="y", x0=50, y0=0, x1=100, y1=60, fillcolor="rgba(239, 68, 68, 0.08)", line_width=0, layer="below"),
    ]

    fig.add_vline(x=50, line_dash="dash", line_color="rgba(148, 163, 184, 0.4)")
    fig.add_hline(y=60, line_dash="dash", line_color="rgba(148, 163, 184, 0.4)")

    annotations = [
        dict(x=25, y=96, text="🟢 <b>JOIAS DA COROA</b><br><span style='font-size:11px;color:#10B981;'>Alto Retorno • Baixo Risco</span>", showarrow=False, font=dict(size=12, color="#10B981")),
        dict(x=25, y=10, text="🔵 <b>FLUXO CONTÍNUO</b><br><span style='font-size:11px;color:#38BDF8;'>Retorno Moderado • Baixo Risco</span>", showarrow=False, font=dict(size=12, color="#38BDF8")),
        dict(x=75, y=96, text="🟣 <b>GRANDES APOSTAS</b><br><span style='font-size:11px;color:#A855F7;'>Alto Retorno • Risco Elevado</span>", showarrow=False, font=dict(size=12, color="#A855F7")),
        dict(x=75, y=10, text="🔴 <b>ARMADILHAS</b><br><span style='font-size:11px;color:#EF4444;'>Baixo Retorno • Alto Risco</span>", showarrow=False, font=dict(size=12, color="#EF4444"))
    ]

    fig.update_layout(
        title=dict(
            text="🎯 Matriz Quali-Quanti: Risco Operacional vs Potencial de Retorno",
            font=dict(size=14, color="#F8FAFC" if is_dark else "#0F172A"),
            y=0.97,
            x=0.01,
            xanchor="left",
            yanchor="top"
        ),
        xaxis=dict(title="Nível de Risco Operacional & Regulatório (0 = Seguro → 100 = Alto Risco)", range=[0, 100], gridcolor="rgba(255,255,255,0.06)" if is_dark else "rgba(0,0,0,0.06)", automargin=True),
        yaxis=dict(title="Potencial de Retorno Financeiro & Margem (0 = Baixo → 100 = Alto)", range=[0, 105], gridcolor="rgba(255,255,255,0.06)" if is_dark else "rgba(0,0,0,0.06)", automargin=True),
        shapes=shapes,
        annotations=annotations,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=550,
        margin=dict(l=45, r=25, t=60, b=55),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.14,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(15, 23, 42, 0.85)" if is_dark else "rgba(255, 255, 255, 0.9)",
            bordercolor="rgba(255, 255, 255, 0.1)" if is_dark else "rgba(0, 0, 0, 0.1)",
            borderwidth=1
        )
    )
    return fig


def build_wsj_timeline_swarm(df, is_dark=True):
    """Constrói a Linha do Tempo Cronológica estilo WSJ Dot Plot / Swarm (Imagem 2)

    com gradiente térmico de urgência/aderência e marcos temporais.
    """
    if df.empty:
        return go.Figure()

    df_plot = df.copy()
    df_plot["valor_fmt"] = df_plot["valor_total_estimado"].apply(formatar_moeda_completa)
    df_plot["dias_display"] = df_plot["dias_restantes"].apply(lambda d: f"{d:.1f} dias")
    df_plot["orgao_curto"] = df_plot["razao_social_orgao"].fillna("Órgão").apply(
        lambda o: str(o)[:38] + "..." if len(str(o)) > 38 else str(o)
    )

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_plot["dias_restantes"],
        y=df_plot["valor_total_estimado"],
        mode="markers",
        marker=dict(
            size=df_plot["score_candidatura"].apply(lambda s: max(10, min(24, int(s / 4.2)))),
            color=df_plot["score_candidatura"],
            colorscale=[
                [0.0, "#EF4444"],
                [0.5, "#F59E0B"],
                [0.75, "#10B981"],
                [1.0, "#00F59B"]
            ],
            cmin=30,
            cmax=100,
            colorbar=dict(
                title=dict(text="Fit Score", font=dict(size=10, color="#94A3B8")),
                thickness=10,
                len=0.7,
                tickfont=dict(size=9, color="#94A3B8")
            ),
            opacity=0.88,
            line=dict(width=1.2, color="#FFFFFF" if is_dark else "#0F172A")
        ),
        text=df_plot["orgao_curto"],
        customdata=list(zip(
            df_plot["score_candidatura"],
            df_plot["decisao_tag"],
            df_plot["dias_display"],
            df_plot["valor_fmt"],
            df_plot["modalidade_nome"],
            df_plot["matched_subtema"],
            df_plot["justificativa_candidatura"],
            df_plot["numero_controle_pncp"]
        )),
        hovertemplate=(
            "<b>%{text}</b><br><br>"
            "🎯 <b>Decisão:</b> %{customdata[1]} (Score: %{customdata[0]}/100)<br>"
            "⏳ <b>Prazo Limite:</b> %{customdata[2]} restantes<br>"
            "💰 <b>Valor Estimado:</b> %{customdata[3]}<br>"
            "🏛️ <b>Modalidade:</b> %{customdata[4]}<br>"
            "📦 <b>Demanda:</b> %{customdata[5]}<br>"
            "⚡ <b>Destaques:</b> %{customdata[6]}<extra></extra>"
        )
    ))

    fig.add_vline(
        x=2.0, line_dash="dash", line_color="rgba(239, 68, 68, 0.7)",
        annotation_text="🚨 Urgente (≤ 48h)", annotation_position="bottom left",
        annotation_font=dict(size=10, color="#EF4444")
    )
    fig.add_vline(
        x=7.0, line_dash="dash", line_color="rgba(245, 158, 11, 0.7)",
        annotation_text="⚡ Curto Prazo (3-7d)", annotation_position="bottom left",
        annotation_font=dict(size=10, color="#F59E0B")
    )

    fig.update_layout(
        title=dict(
            text="📅 Linha do Tempo Cronológica: Prazo Restante vs Valor Estimado",
            font=dict(size=13, color="#F8FAFC" if is_dark else "#0F172A"),
            y=0.97,
            x=0.01,
            xanchor="left",
            yanchor="top"
        ),
        xaxis=dict(
            title="Dias Restantes até o Encerramento de Propostas",
            gridcolor="rgba(255,255,255,0.06)" if is_dark else "rgba(0,0,0,0.06)",
            zeroline=False,
            tickfont=dict(color="#94A3B8"),
            automargin=True
        ),
        yaxis=dict(
            title="Valor Estimado do Contrato (R$)",
            type="log",
            gridcolor="rgba(255,255,255,0.06)" if is_dark else "rgba(0,0,0,0.06)",
            zeroline=False,
            tickfont=dict(color="#94A3B8"),
            automargin=True
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=520,
        margin=dict(l=45, r=25, t=55, b=45)
    )
    return fig


def render_executive_kpis(kpis_data):
    """Renderiza a faixa de cartões de KPI no padrão executivo Power BI."""
    col1, col2, col3, col4, col5 = st.columns(5)

    cards_info = [
        {
            "col": col1,
            "title": "EDITAIS MAPEADOS",
            "value": formatar_inteiro(kpis_data['total_editais']),
            "sub": "Base ativa de 2 anos",
            "icon": "📄",
            "accent": "#3B82F6",
        },
        {
            "col": col2,
            "title": "VOLUME ESTIMADO",
            "value": formatar_moeda_compacta(kpis_data['valor_total_estimado']),
            "sub": formatar_moeda_completa(kpis_data['valor_total_estimado']),
            "icon": "💰",
            "accent": "#10B981",
        },
        {
            "col": col3,
            "title": "TICKET MÉDIO",
            "value": formatar_moeda_compacta(kpis_data['ticket_medio']),
            "sub": formatar_moeda_completa(kpis_data['ticket_medio']),
            "icon": "🎯",
            "accent": "#F59E0B",
        },
        {
            "col": col4,
            "title": "ÓRGÃOS COMPRADORES",
            "value": formatar_inteiro(kpis_data['total_orgaos']),
            "sub": "Prefeituras & Secretarias",
            "icon": "🏛️",
            "accent": "#8B5CF6",
        },
        {
            "col": col5,
            "title": "DESÁGIO MÉDIO",
            "value": formatar_percentual(kpis_data['desagio_medio_pct']),
            "sub": "Economia licitatória",
            "icon": "📉",
            "accent": "#06B6D4",
        },
    ]

    for c in cards_info:
        with c["col"]:
            st.markdown(f"""
            <div class="pbi-kpi-card" style="border-top: 3.5px solid {c['accent']};">
                <div class="pbi-kpi-header">
                    <span class="pbi-kpi-title">{c['title']}</span>
                    <span class="pbi-kpi-icon">{c['icon']}</span>
                </div>
                <div class="pbi-kpi-value">{c['value']}</div>
                <div class="pbi-kpi-sub" title="{c['sub']}">{c['sub']}</div>
            </div>
            """, unsafe_allow_html=True)


# Carrega os dados brutos
df_raw = analytics.get_dataframe()
# Filtro Principal: Manter apenas os editais que deram MATCH com o perfil B2G da empresa (Carlos e Felipe)
if not df_raw.empty and "matched_category" in df_raw.columns:
    df_raw = df_raw[df_raw["matched_category"].notna() & (df_raw["matched_category"] != "")]
df_itens_raw = analytics.get_itens_dataframe()

# Header Executivo Estilo Power BI Top Tabs
total_raw_ed = formatar_inteiro(len(df_raw)) if not df_raw.empty else "0"
total_raw_vol = formatar_moeda_compacta(df_raw["valor_total_estimado"].sum()) if not df_raw.empty else "R$ 0,00"

st.markdown(f"""
<div class="pbi-top-banner">
    <div class="pbi-banner-left">
        <div class="pbi-banner-icon">🏛️</div>
        <div>
            <div class="pbi-banner-title">Radar de Compras Públicas & Inteligência PNCP</div>
            <div class="pbi-banner-subtitle">Painel Analítico de Oportunidades Governamentais • Lei 14.133/2021 • Malha 250 km • {layout_style}</div>
        </div>
    </div>
    <div class="pbi-banner-right">
        <div class="pbi-badge active">
            <span class="pulse-dot"></span>
            <span>{total_raw_ed} EDITAIS INDEXADOS</span>
        </div>
        <div class="pbi-badge">
            <span>{total_raw_vol} MAPEADOS</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Barra Lateral: Estilo Power BI Filter Panel (Layout 05)
st.sidebar.markdown("""
<div class="sidebar-header-card">
    <div style="font-size: 22px;">🔍</div>
    <div>
        <div class="sidebar-header-title">Painel de Filtros</div>
        <div class="sidebar-header-sub">Layout 05: Filter Panel</div>
    </div>
</div>
""", unsafe_allow_html=True)

if not df_raw.empty:
    # 1. Filtro de Categorias Temáticas
    categorias_disponiveis = [c for c in df_raw["matched_category"].dropna().unique() if c]
    cat_selected = st.sidebar.multiselect("Categoria Temática:", options=categorias_disponiveis, default=categorias_disponiveis)

    # 2. Filtro de Subtemas
    subtemas_disponiveis = [s for s in df_raw[df_raw["matched_category"].isin(cat_selected)]["matched_subtema"].dropna().unique() if s]
    sub_selected = st.sidebar.multiselect("Subtemas:", options=subtemas_disponiveis, default=subtemas_disponiveis)

    # 3. Filtro de Estados (UF)
    ufs_disponiveis = sorted([u for u in df_raw["uf_sigla"].dropna().unique() if u])
    uf_selected = st.sidebar.multiselect("Unidades da Federação (UF):", options=ufs_disponiveis, default=ufs_disponiveis)

    # 4. Filtro de Modalidade
    modalidades_disponiveis = sorted([m for m in df_raw["modalidade_nome"].dropna().unique() if m])
    mod_selected = st.sidebar.multiselect("Modalidade:", options=modalidades_disponiveis, default=modalidades_disponiveis)

    # 5. Filtro Logístico: As 9 Bases Operacionais
    bases_disponiveis = [b for b in df_raw["base_logistica"].dropna().unique() if b and b != "Outro"]
    base_selected = st.sidebar.multiselect("Hub Logístico (9 Bases):", options=bases_disponiveis, default=bases_disponiveis)
    only_priority_geo = st.sidebar.checkbox("🎯 Apenas Bases Estratégicas (Raio <= 250km ou Remoto)", value=False)

    # 6. Busca textual livre no objeto
    search_term = st.sidebar.text_input("Buscar palavra no Objeto:", placeholder="Ex: ideb, saeb, software, nuvem...")

    # Aplicação dos filtros
    filtered_df = df_raw.copy()
    if cat_selected:
        filtered_df = filtered_df[filtered_df["matched_category"].isin(cat_selected)]
    if sub_selected:
        filtered_df = filtered_df[filtered_df["matched_subtema"].isin(sub_selected)]
    if uf_selected:
        filtered_df = filtered_df[filtered_df["uf_sigla"].isin(uf_selected)]
    if mod_selected:
        filtered_df = filtered_df[filtered_df["modalidade_nome"].isin(mod_selected)]
    if base_selected and "base_logistica" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["base_logistica"].isin(base_selected) | (filtered_df["base_logistica"].isna())]
    if only_priority_geo and "is_priority_geo" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["is_priority_geo"] == 1]
    if search_term:
        filtered_df = filtered_df[filtered_df["objeto_compra"].str.contains(search_term, case=False, na=False)]

    # Status Dinâmico de Filtro (Layout 05)
    pct_filtrado = (len(filtered_df) / len(df_raw) * 100) if len(df_raw) > 0 else 0
    st.sidebar.markdown(f"""
    <div class="pbi-filter-status">
        <b>Filtro Ativo:</b> {formatar_inteiro(len(filtered_df))} de {formatar_inteiro(len(df_raw))} editais ({pct_filtrado:.1f}%)
        <div class="pbi-progress-bar">
            <div class="pbi-progress-fill" style="width: {pct_filtrado:.1f}%;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # -------------------------------------------------------------
    # MOTOR DE DECISÃO TÁTICA (4 PILARES) - GAVETA ESQUERDA
    # -------------------------------------------------------------
    st.sidebar.markdown("""
    <div style="padding: 10px 12px; background: rgba(59, 130, 246, 0.08); border-left: 3px solid #3B82F6; border-radius: 6px; margin-top: 14px; margin-bottom: 8px;">
        <div style="font-size: 11px; font-weight: 800; color: #3B82F6; letter-spacing: 0.05em; text-transform: uppercase;">
            ⚖️ Pesos de Decisão (4 Pilares)
        </div>
        <div style="font-size: 10px; color: #94A3B8; margin-top: 2px;">
            Ajuste fino do motor Datadriven de recomendação
        </div>
    </div>
    """, unsafe_allow_html=True)

    peso_aderencia = st.sidebar.slider(
        "🎯 Aderência Técnica / Temática",
        min_value=0, max_value=100, value=35, step=5,
        help="Alinhamento com TI, SaaS, Nuvem, IA, Dados, IDEB e Educação."
    )
    peso_custo = st.sidebar.slider(
        "💰 Custo-Benefício & Ticket",
        min_value=0, max_value=100, value=25, step=5,
        help="Atratividade financeira e ticket ideal (R$ 50k a R$ 1.5M)."
    )
    peso_logistica = st.sidebar.slider(
        "🚚 Logística & Proximidade 9 Bases",
        min_value=0, max_value=100, value=25, step=5,
        help="Proximidade geográfica dos 9 hubs ou entregas 100% remotas/nuvem."
    )
    peso_historico = st.sidebar.slider(
        "🏛️ Histórico & Fricção da Modalidade",
        min_value=0, max_value=100, value=15, step=5,
        help="Modalidades de menor fricção (Dispensa, Credenciamento, Pregão)."
    )

    tot_p = max(1, peso_aderencia + peso_custo + peso_logistica + peso_historico)
    p_ad_pct = int(round(peso_aderencia / tot_p * 100))
    p_cu_pct = int(round(peso_custo / tot_p * 100))
    p_lo_pct = int(round(peso_logistica / tot_p * 100))
    p_hi_pct = int(round(peso_historico / tot_p * 100))

    st.sidebar.caption(f"Distribuição: **{p_ad_pct}%** Aderência • **{p_cu_pct}%** Custo • **{p_lo_pct}%** Logística • **{p_hi_pct}%** Histórico")
else:
    filtered_df = pd.DataFrame()
    peso_aderencia, peso_custo, peso_logistica, peso_historico = 35, 25, 25, 15

# Cartões Executivos de KPI (Power BI Cards)
kpis = analytics.summary_kpis(filtered_df)
render_executive_kpis(kpis)

# -------------------------------------------------------------
# MENU EXECUTIVO DE NAVEGAÇÃO NA BARRA LATERAL (SUBSTITUI ABAS DE TOPO)
# -------------------------------------------------------------
st.sidebar.markdown("""
<div style="margin-top: 16px; margin-bottom: 8px;">
    <div style="font-size: 11px; font-weight: 800; color: #64748B; letter-spacing: 0.08em; text-transform: uppercase;">
        📑 Módulos Executivos
    </div>
</div>
""", unsafe_allow_html=True)

menu_navegacao = st.sidebar.radio(
    "Navegação do Sistema:",
    [
        "📊 1. Visão Geral",
        "🧠 2. Contexto",
        "🔍 3. Detalhes",
        "🛡️ 4. Observabilidade",
        "🦅 5. I.C.A.R.O. (Agências & Privado)"
    ],
    index=0,
    label_visibility="collapsed"
)

# ----------------- MÓDULO 1: RADAR DE CANDIDATURA (EDITAIS ABERTOS) -----------------
if menu_navegacao == "📊 1. Visão Geral":
    st.subheader("🎯 Command Center de Candidatura: Widescreen Dataviz & Datadriven")
    st.caption(
        "Fluxo tático em 3 partes centrais com gavetas laterais de inteligência. "
        "O motor pondera **Histórico, Aderência, Custo-Benefício e Logística** em tempo real com os pesos definidos no painel deslizante à esquerda."
    )

    if not filtered_df.empty:
        try:
            df_cand_raw = analytics.live_candidacy_radar(
                filtered_df,
                peso_aderencia=peso_aderencia,
                peso_custo_beneficio=peso_custo,
                peso_logistica=peso_logistica,
                peso_historico=peso_historico,
                apenas_abertos=False,
            )
        except TypeError:
            df_cand_raw = analytics.live_candidacy_radar(
                filtered_df,
                peso_aderencia=peso_aderencia,
                peso_custo_beneficio=peso_custo,
                peso_logistica=peso_logistica,
                peso_historico=peso_historico,
            )

        if not df_cand_raw.empty:
            # 1. Faixa de KPIs Executivos do Pipeline Mapeado
            tot_mapeados = len(df_cand_raw)
            tot_abertos = int((df_cand_raw["dias_restantes"] > 0).sum())
            vol_aberto = df_cand_raw[df_cand_raw["dias_restantes"] > 0]["valor_total_estimado"].sum()
            vol_total = df_cand_raw["valor_total_estimado"].sum()
            alta_rec_count = int((df_cand_raw["score_candidatura"] >= 75).sum())
            dispensas_count = int(df_cand_raw["modalidade_nome"].fillna("").astype(str).str.lower().str.contains("dispensa").sum())

            c_kpi1, c_kpi2, c_kpi3, c_kpi4 = st.columns(4)
            c_kpi1.metric("Oportunidades no Radar", f"{formatar_inteiro(tot_mapeados)} editais", f"{tot_abertos} abertas hoje")
            c_kpi2.metric("Pipeline Mapeado", formatar_moeda_compacta(vol_total), help=f"Pipeline com propostas abertas hoje: {formatar_moeda_completa(vol_aberto)}")
            c_kpi3.metric("Altamente Recomendados", f"{formatar_inteiro(alta_rec_count)} editais", "Score ≥ 75 (Forte Fit)")
            c_kpi4.metric("Dispensas Eletrônicas", f"{formatar_inteiro(dispensas_count)} compras", "Vitória ágil / Baixa burocracia")

            st.markdown("---")

            # 2. Barra de Filtros Táticos no Próprio Painel
            st.markdown("#### ⚡ Filtros Táticos de Sugestão de Candidatura")
            f_col1, f_col2, f_col3, f_col4 = st.columns(4)

            with f_col1:
                filtro_rec = st.selectbox(
                    "Sugerir Minha Candidatura / Escopo:",
                    [
                        "🏛️ Mercado Mapeado Completo (Todos os Editais)",
                        "🎯 Pipeline Aberto (Propostas Ativas Hoje)",
                        "🟢 Apenas Alta Recomendação (Score ≥ 75)",
                        "🟡 Viáveis ou Superiores (Score ≥ 50)",
                    ],
                    index=0
                )

            with f_col2:
                filtro_prazo = st.selectbox(
                    "Janela de Prazo Restante:",
                    [
                        "Todas as Janelas de Prazo",
                        "🚨 Urgente (Até 48 horas)",
                        "⚡ Prazo Curto (3 a 7 dias)",
                        "🎯 Janela Ampla (Mais de 7 dias)",
                        "⏳ Propostas Encerradas / Base Histórica"
                    ],
                    index=0
                )

            with f_col3:
                mod_opcoes = [
                    "Todas as Modalidades",
                    "Dispensa (Eletrônica / Direta)",
                    "Pregão Eletrônico",
                    "Concorrência",
                    "Credenciamento"
                ]
                filtro_mod = st.selectbox("Modalidade Competitiva:", mod_opcoes, index=0)

            with f_col4:
                filtro_geo = st.selectbox(
                    "Fit Logístico / Raio:",
                    [
                        "Todas as Localidades",
                        "🎯 Apenas Remoto / SaaS ou Raio ≤ 250km"
                    ],
                    index=0
                )

            # Aplicação dos filtros do painel
            df_cand = df_cand_raw.copy()

            if "Pipeline Aberto" in filtro_rec:
                df_cand = df_cand[df_cand["dias_restantes"] > 0.0]
            elif "Alta Recomendação" in filtro_rec:
                df_cand = df_cand[df_cand["score_candidatura"] >= 75]
            elif "Viáveis" in filtro_rec:
                df_cand = df_cand[df_cand["score_candidatura"] >= 50]

            if "Urgente" in filtro_prazo:
                df_cand = df_cand[(df_cand["dias_restantes"] > 0.0) & (df_cand["dias_restantes"] <= 2.0)]
            elif "Prazo Curto" in filtro_prazo:
                df_cand = df_cand[(df_cand["dias_restantes"] > 2.0) & (df_cand["dias_restantes"] <= 7.0)]
            elif "Janela Ampla" in filtro_prazo:
                df_cand = df_cand[df_cand["dias_restantes"] > 7.0]
            elif "Encerradas" in filtro_prazo or "Histórica" in filtro_prazo:
                df_cand = df_cand[df_cand["dias_restantes"] <= 0.0]

            if "dispensa" in filtro_mod.lower():
                df_cand = df_cand[df_cand["modalidade_nome"].fillna("").astype(str).str.lower().str.contains("dispensa")]
            elif "pregão" in filtro_mod.lower():
                df_cand = df_cand[df_cand["modalidade_nome"].fillna("").astype(str).str.lower().str.contains("pregão")]
            elif "concorrência" in filtro_mod.lower():
                df_cand = df_cand[df_cand["modalidade_nome"].fillna("").astype(str).str.lower().str.contains("concorrência")]
            elif "credenciamento" in filtro_mod.lower():
                df_cand = df_cand[df_cand["modalidade_nome"].fillna("").astype(str).str.lower().str.contains("credenciamento")]
            elif filtro_mod != "Todas as Modalidades":
                df_cand = df_cand[df_cand["modalidade_nome"] == filtro_mod]

            if "250km" in filtro_geo:
                df_cand = df_cand[
                    (df_cand["distancia_km"] <= 250.0) |
                    (df_cand["base_logistica"].fillna("").str.lower().str.contains("remoto")) |
                    (df_cand["matched_subtema"].fillna("").str.lower().str.contains("software|cloud|saas|dados|ia"))
                ]

            col_inf_l, col_inf_r = st.columns([1.5, 1])
            with col_inf_l:
                st.caption(f"Mostrando **{formatar_inteiro(len(df_cand))}** de **{formatar_inteiro(tot_mapeados)}** editais com base nos critérios de candidatura.")
            with col_inf_r:
                modo_view_cc = st.radio(
                    "Visualização do Command Center:",
                    ["🌟 Dataviz Widescreen em Destaque", "📐 Painel Triplo em Colunas"],
                    horizontal=True,
                    label_visibility="collapsed",
                    key="modo_view_cc_radio"
                )

            if not df_cand.empty:
                # Gerenciamento de Edital Ativo em Inspeção nas Gavetas
                if "edital_ativo_pncp" not in st.session_state or not st.session_state["edital_ativo_pncp"]:
                    st.session_state["edital_ativo_pncp"] = df_cand.iloc[0]["numero_controle_pncp"]
                elif st.session_state["edital_ativo_pncp"] not in df_cand["numero_controle_pncp"].values:
                    st.session_state["edital_ativo_pncp"] = df_cand.iloc[0]["numero_controle_pncp"]

                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

                qtd_go = int((df_cand["decisao_tag"] == "🟢 GO").sum())
                vol_go = df_cand[df_cand["decisao_tag"] == "🟢 GO"]["valor_total_estimado"].sum()
                qtd_watch = int((df_cand["decisao_tag"] == "🟡 WATCH").sum())
                vol_watch = df_cand[df_cand["decisao_tag"] == "🟡 WATCH"]["valor_total_estimado"].sum()
                qtd_nogo = int((df_cand["decisao_tag"] == "🔴 NO-GO").sum())
                vol_nogo = df_cand[df_cand["decisao_tag"] == "🔴 NO-GO"]["valor_total_estimado"].sum()

                # Lista de ramos / subtemas para navegação interativa
                sub_counts = df_cand["matched_subtema"].value_counts().to_dict()
                ramos_opcoes = [f"🌟 Todos os Ramos ({len(df_cand)} editais)"]
                subtemas_ordem = [
                    "Inteligência Artificial & Machine Learning",
                    "Privacidade & Proteção de Dados (LGPD)",
                    "Governança Pública & Planejamento",
                    "Consultoria & Assessoria Técnica Especializada",
                    "Avaliação Educacional, IDEB & VAAR",
                    "Business Intelligence & Dashboards",
                    "Pensamento Computacional & STEAM",
                    "Engenharia de Dados & Infraestrutura Cloud",
                    "Políticas Educacionais & Educação Básica",
                    "Tecnologias & Inovação Educacional",
                    "Gestão de Projetos & Processos (PMO / BPM)",
                    "Monitoramento & Avaliação (M&A / MEL)",
                    "Transformação & Governo Digital",
                    "Ciência de Dados & Analytics"
                ]
                icon_map = {
                    "Inteligência Artificial & Machine Learning": "🤖",
                    "Privacidade & Proteção de Dados (LGPD)": "🔒",
                    "Governança Pública & Planejamento": "🏛️",
                    "Consultoria & Assessoria Técnica Especializada": "📑",
                    "Avaliação Educacional, IDEB & VAAR": "🟢",
                    "Business Intelligence & Dashboards": "📊",
                    "Pensamento Computacional & STEAM": "🌸",
                    "Engenharia de Dados & Infraestrutura Cloud": "🗄️",
                    "Políticas Educacionais & Educação Básica": "🟤",
                    "Tecnologias & Inovação Educacional": "📙",
                    "Gestão de Projetos & Processos (PMO / BPM)": "⚡",
                    "Monitoramento & Avaliação (M&A / MEL)": "🎯",
                    "Transformação & Governo Digital": "🌐",
                    "Ciência de Dados & Analytics": "🔬",
                }
                for st_nome in subtemas_ordem:
                    qtd_st = sub_counts.get(st_nome, 0)
                    if qtd_st > 0:
                        icon = icon_map.get(st_nome, "📁")
                        ramos_opcoes.append(f"{icon} {st_nome} ({qtd_st} editais)")

                if "Widescreen" in modo_view_cc:
                    # ==============================================================
                    # MODO 1: DATAVIZ WIDESCREEN EM DESTAQUE COM NAVEGAÇÃO INTERATIVA
                    # ==============================================================
                    # 1. Funil de Decisão Rápida em Faixa Superior
                    c_f1, c_f2, c_f3 = st.columns(3)
                    with c_f1:
                        st.markdown(f"""
                        <div class="radar-stat-box" style="border-left: 5px solid #10B981; padding: 12px 16px;">
                            <div>
                                <div style="font-weight: 800; color: #10B981; font-size: 13.5px;">🟢 GO (Candidatura Recomendada)</div>
                                <div style="font-size: 11.5px; color: {c_text_secondary};">{formatar_moeda_compacta(vol_go)} em volume</div>
                            </div>
                            <div style="font-size: 24px; font-weight: 800; color: #10B981;">{formatar_inteiro(qtd_go)}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with c_f2:
                        st.markdown(f"""
                        <div class="radar-stat-box" style="border-left: 5px solid #F59E0B; padding: 12px 16px;">
                            <div>
                                <div style="font-weight: 800; color: #F59E0B; font-size: 13.5px;">🟡 WATCH (Avaliar Viabilidade)</div>
                                <div style="font-size: 11.5px; color: {c_text_secondary};">{formatar_moeda_compacta(vol_watch)} em volume</div>
                            </div>
                            <div style="font-size: 24px; font-weight: 800; color: #F59E0B;">{formatar_inteiro(qtd_watch)}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with c_f3:
                        st.markdown(f"""
                        <div class="radar-stat-box" style="border-left: 5px solid #EF4444; padding: 12px 16px;">
                            <div>
                                <div style="font-weight: 800; color: #EF4444; font-size: 13.5px;">🔴 NO-GO (Baixa Prioridade)</div>
                                <div style="font-size: 11.5px; color: {c_text_secondary};">{formatar_moeda_compacta(vol_nogo)} em volume</div>
                            </div>
                            <div style="font-size: 24px; font-weight: 800; color: #EF4444;">{formatar_inteiro(qtd_nogo)}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    # 2. Dataviz Central de Inteligência em Destaque Widescreen
                    st.markdown("""
                    <div style="margin-top: 14px; margin-bottom: 8px; padding: 10px 16px; background: rgba(59, 130, 246, 0.08); border-radius: 10px; border: 1px solid rgba(59, 130, 246, 0.25); display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 15px; font-weight: 800; color: #38BDF8;">📊 2. Dataviz Central: Ramificações Alluvial & Linha do Tempo</span>
                        <span style="font-size: 12px; color: #94A3B8;">Visão Panorâmica Widescreen & Navegação por Ramos</span>
                    </div>
                    """, unsafe_allow_html=True)

                    c_ctrl1, c_ctrl2, c_ctrl3 = st.columns([1.1, 1.1, 1.8])
                    with c_ctrl1:
                        tipo_dataviz = st.radio(
                            "Modo Dataviz:",
                            ["🌿 Ramificações (Sankey Flow)", "📅 Linha do Tempo (WSJ Swarm)"],
                            horizontal=True,
                            key="tipo_dv_wide"
                        )
                    with c_ctrl2:
                        escopo_sankey = st.radio(
                            "Base do Dataviz:",
                            ["🏛️ Mercado Mapeado Completo", "🎯 Pipeline Aberto"],
                            horizontal=True,
                            key="escopo_dv_wide"
                        )
                    with c_ctrl3:
                        sel_ramo_drill = st.selectbox(
                            "🧭 Navegar no Ramo do Dataviz para Filtrar:",
                            ramos_opcoes,
                            index=0,
                            key="sb_ramo_drill_wide"
                        )

                    # Filtro do ramo selecionado
                    if "Todos os Ramos" in sel_ramo_drill:
                        df_ramo_cand = df_cand
                        nome_ramo_ativo = "Todos os Ramos"
                    else:
                        nome_ramo_ativo = sel_ramo_drill.split(" (")[0][2:].strip()
                        df_ramo_cand = df_cand[df_cand["matched_subtema"] == nome_ramo_ativo]
                        if df_ramo_cand.empty:
                            df_ramo_cand = df_cand

                    if "Ramificações" in tipo_dataviz:
                        df_sank_input = df_cand if "Pipeline Aberto" in escopo_sankey else (df_cand_raw if "df_cand_raw" in locals() and df_cand_raw is not None else filtered_df)
                        if nome_ramo_ativo != "Todos os Ramos":
                            df_sank_input = df_sank_input[df_sank_input["matched_subtema"] == nome_ramo_ativo]
                        render_interactive_sankey_widescreen(df_sank_input, is_dark=is_dark)
                        st.caption("🌿 **Fluxo de Ramificações Alluvial:** Mapeia Modalidade ➔ Vertical Estratégica ➔ Subtema Especializado ➔ Decisão Estratégica. Passe o mouse sobre os nós ou fluxos à esquerda para listar instantaneamente os editais com links diretos no radar lateral.")
                    else:
                        fig_wsj = build_wsj_timeline_swarm(df_ramo_cand, is_dark=is_dark)
                        st.plotly_chart(fig_wsj, use_container_width=True)
                        st.caption("📅 **Linha do Tempo Cronológica:** Prazos no eixo X vs Valor no eixo Y com gradiente de calor. Selecione os editais abaixo para inspecionar.")

                    # 3. Resumo Executivo & Acesso Imediato ao Edital
                    st.markdown("---")
                    st.markdown(f"##### 📋 3. Resumo Executivo & Seleção Imediata do Edital • <span style='color: #38BDF8;'>{nome_ramo_ativo} ({len(df_ramo_cand)} editais)</span>", unsafe_allow_html=True)

                    c_card_resumo, c_grid_feed = st.columns([1.15, 1.35], gap="large")

                    # Coluna 1: Card de Resumo Executivo com Botão Clicável PNCP
                    with c_card_resumo:
                        st.markdown("###### 🔍 Edital Selecionado para Ação Imediata:")
                        opcoes_edital_ramo = [
                            f"[{r['score_candidatura']} pts] {r['razao_social_orgao'][:38]} • {formatar_moeda_compacta(r['valor_total_estimado'])}"
                            for _, r in df_ramo_cand.iterrows()
                        ]
                        pncp_edital_ramo = df_ramo_cand["numero_controle_pncp"].tolist()
                        idx_sel_ramo = 0
                        if st.session_state.get("edital_ativo_pncp") in pncp_edital_ramo:
                            idx_sel_ramo = pncp_edital_ramo.index(st.session_state["edital_ativo_pncp"])

                        edital_escolhido = st.selectbox(
                            "Escolha um edital para inspecionar:",
                            opcoes_edital_ramo,
                            index=idx_sel_ramo,
                            key="sb_edital_resumo_direto"
                        )
                        if edital_escolhido:
                            pncp_num_sel = pncp_edital_ramo[opcoes_edital_ramo.index(edital_escolhido)]
                            if st.session_state.get("edital_ativo_pncp") != pncp_num_sel:
                                st.session_state["edital_ativo_pncp"] = pncp_num_sel
                                st.rerun()

                        row_sel_match = df_ramo_cand[df_ramo_cand["numero_controle_pncp"] == st.session_state.get("edital_ativo_pncp")]
                        row_sel = row_sel_match.iloc[0] if not row_sel_match.empty else df_ramo_cand.iloc[0]

                        dec_cor = "#10B981" if "GO" in str(row_sel["decisao_tag"]) else ("#F59E0B" if "WATCH" in str(row_sel["decisao_tag"]) else "#EF4444")
                        prazo_txt = f"⏳ {row_sel['dias_restantes']:.1f}d restantes" if row_sel['dias_restantes'] > 0 else "⏳ Proposta Encerrada"

                        obj_limpo = html.escape(str(row_sel.get("objeto_compra", ""))).strip().replace("\n", "<br>")
                        orgao_limpo = html.escape(str(row_sel.get("razao_social_orgao", ""))).strip()
                        uf_limpo = html.escape(str(row_sel.get("uf_sigla", ""))).strip()
                        modalidade_limpo = html.escape(str(row_sel.get("modalidade_nome", ""))).strip()
                        subtema_limpo = html.escape(str(row_sel.get("matched_subtema", ""))).strip()
                        kw_limpo = html.escape(str(row_sel.get("matched_keywords", ""))).strip()
                        pncp_limpo = html.escape(str(row_sel.get("numero_controle_pncp", ""))).strip()
                        decisao_limpo = html.escape(str(row_sel.get("decisao_tag", ""))).strip()
                        bg_obj = "rgba(255,255,255,0.04)" if is_dark else "rgba(0,0,0,0.03)"

                        card_html = (
                            f'<div style="background: {c_card_bg}; border: 2px solid {dec_cor}; border-radius: 12px; padding: 16px 18px; margin-bottom: 12px; box-shadow: {c_card_shadow};">'
                            f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">'
                            f'<span style="font-size: 13px; font-weight: 800; color: {dec_cor}; background: rgba(16, 185, 129, 0.12); padding: 4px 10px; border-radius: 6px;">'
                            f'{decisao_limpo} • Fit Score: {row_sel["score_candidatura"]}/100</span>'
                            f'<span style="font-size: 12px; color: {c_text_secondary}; font-weight: 700;">{prazo_txt}</span>'
                            f'</div>'
                            f'<div style="font-size: 14px; font-weight: 800; color: {c_text_primary}; margin-bottom: 4px;">🏛️ {orgao_limpo} ({uf_limpo})</div>'
                            f'<div style="font-size: 11.5px; color: {c_text_secondary}; margin-bottom: 10px;">'
                            f'PNCP: <code>{pncp_limpo}</code><br>'
                            f'Modalidade: <b>{modalidade_limpo}</b> • Valor: <b>{formatar_moeda_completa(row_sel["valor_total_estimado"])}</b>'
                            f'</div>'
                            f'<div style="font-size: 12px; font-weight: 700; color: #3B82F6; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.05em;">📝 Resumo Executivo do Objeto:</div>'
                            f'<div style="font-size: 12.5px; line-height: 1.5; color: {c_text_primary}; background: {bg_obj}; padding: 10px 12px; border-radius: 8px; border-left: 3px solid #3B82F6; margin-bottom: 10px;">'
                            f'{obj_limpo}'
                            f'</div>'
                            f'<div style="font-size: 11px; color: {c_text_secondary}; margin-bottom: 10px;">'
                            f'🎯 <b>Especialidade:</b> {subtema_limpo}<br>'
                            f'🔑 <b>Termos-chave:</b> <span style="color: #38BDF8;">{kw_limpo}</span>'
                            f'</div>'
                            f'<div class="pillar-row" style="margin-top: 6px;">'
                            f'<span>🎯 Aderência: <b>{row_sel["score_aderencia"]}%</b></span> '
                            f'<span>💰 Custo: <b>{row_sel["score_custo_beneficio"]}%</b></span> '
                            f'<span>🚚 Logística: <b>{row_sel["score_logistica"]}%</b></span> '
                            f'<span>🏛️ Histórico: <b>{row_sel["score_historico"]}%</b></span>'
                            f'</div>'
                            f'</div>'
                        )
                        st.markdown(card_html, unsafe_allow_html=True)

                        # BOTÃO CLICÁVEL DIRETO AO PNCP
                        st.link_button(
                            "🌐 Abrir Edital Oficial Completo no Portal do PNCP ↗",
                            row_sel["url_oficial_edital"],
                            type="primary",
                            use_container_width=True
                        )

                    # Coluna 2: Grid / Tabela com Links Clicáveis
                    with c_grid_feed:
                        st.markdown("###### 📋 Tabela de Oportunidades do Ramo:")
                        busca_feed_txt = st.text_input("Filtrar nesta lista:", placeholder="Buscar órgão ou palavra...", key="txt_busca_feed_wide")
                        df_feed_show = df_ramo_cand.copy()
                        if busca_feed_txt:
                            df_feed_show = df_feed_show[
                                df_feed_show["objeto_compra"].str.contains(busca_feed_txt, case=False, na=False) |
                                df_feed_show["razao_social_orgao"].str.contains(busca_feed_txt, case=False, na=False)
                            ]

                        df_tab = df_feed_show[[
                            "decisao_tag", "score_candidatura", "dias_restantes",
                            "razao_social_orgao", "uf_sigla", "modalidade_nome", "matched_subtema",
                            "valor_total_estimado", "url_oficial_edital"
                        ]].copy()
                        df_tab["Prazo"] = df_tab["dias_restantes"].apply(lambda d: f"⏳ {d:.1f}d" if d > 0 else "⏳ Encerrado")
                        df_tab["Valor Estimado"] = df_tab["valor_total_estimado"].apply(formatar_moeda_completa)

                        st.dataframe(
                            df_tab[[
                                "decisao_tag", "score_candidatura", "Prazo", "razao_social_orgao", "uf_sigla",
                                "modalidade_nome", "Valor Estimado", "url_oficial_edital"
                            ]].rename(columns={
                                "decisao_tag": "Decisão",
                                "score_candidatura": "Fit Score",
                                "razao_social_orgao": "Órgão Contratante",
                                "uf_sigla": "UF",
                                "modalidade_nome": "Modalidade",
                                "url_oficial_edital": "Edital Oficial"
                            }),
                            column_config={
                                "Edital Oficial": st.column_config.LinkColumn("Edital no PNCP", display_text="🔗 Abrir no PNCP"),
                                "Fit Score": st.column_config.ProgressColumn("Fit Score", min_value=0, max_value=100, format="%d pts"),
                                "Decisão": st.column_config.TextColumn("Decisão", width="small"),
                                "Prazo": st.column_config.TextColumn("Prazo", width="small"),
                                "UF": st.column_config.TextColumn("UF", width="small"),
                            },
                            hide_index=True,
                            use_container_width=True,
                            height=480
                        )

                else:
                    # ==============================================================
                    # MODO 2: PAINEL TRIPLO EM COLUNAS (COMPACTO)
                    # ==============================================================
                    c_funil, c_dataviz, c_feed = st.columns([1.05, 1.45, 1.5], gap="medium")
                    with c_funil:
                        st.markdown("##### 🚦 1. Funil & Decisão Rápida")
                        st.caption("Triagem imediata por probabilidade de vitória")
                        st.markdown(f"""
                        <div class="radar-stat-box" style="border-left: 4px solid #10B981;">
                            <div>
                                <div style="font-weight: 700; color: #10B981; font-size: 13px;">🟢 GO (Candidatura Recomendada)</div>
                                <div style="font-size: 11px; color: {c_text_secondary};">{formatar_moeda_compacta(vol_go)} em disputa</div>
                            </div>
                            <div style="font-size: 20px; font-weight: 800; color: #10B981;">{formatar_inteiro(qtd_go)}</div>
                        </div>
                        <div class="radar-stat-box" style="border-left: 4px solid #F59E0B;">
                            <div>
                                <div style="font-weight: 700; color: #F59E0B; font-size: 13px;">🟡 WATCH (Avaliar Viabilidade)</div>
                                <div style="font-size: 11px; color: {c_text_secondary};">{formatar_moeda_compacta(vol_watch)} em disputa</div>
                            </div>
                            <div style="font-size: 20px; font-weight: 800; color: #F59E0B;">{formatar_inteiro(qtd_watch)}</div>
                        </div>
                        <div class="radar-stat-box" style="border-left: 4px solid #EF4444;">
                            <div>
                                <div style="font-weight: 700; color: #EF4444; font-size: 13px;">🔴 NO-GO (Baixa Prioridade)</div>
                                <div style="font-size: 11px; color: {c_text_secondary};">{formatar_moeda_compacta(vol_nogo)} em disputa</div>
                            </div>
                            <div style="font-size: 20px; font-weight: 800; color: #EF4444;">{formatar_inteiro(qtd_nogo)}</div>
                        </div>
                        """, unsafe_allow_html=True)

                        st.markdown("###### ⭐ Top Oportunidades Imediatas")
                        for idx_card, r_card in df_cand.head(5).iterrows():
                            pncp_num = r_card["numero_controle_pncp"]
                            is_active_card = (pncp_num == st.session_state.get("edital_ativo_pncp"))
                            border_color = "#3B82F6" if is_active_card else ("#10B981" if r_card["score_candidatura"] >= 75 else "#F59E0B")

                            st.markdown(f"""
                            <div class="candidacy-card-item" style="border-left-color: {border_color}; {'background: rgba(59, 130, 246, 0.12);' if is_active_card else ''}">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                                    <span style="font-size: 11.5px; font-weight: 800; color: {border_color};">{r_card['decisao_tag']}</span>
                                    <span style="font-size: 12px; font-weight: 800; background: rgba(59, 130, 246, 0.2); padding: 2px 7px; border-radius: 6px;">{r_card['score_candidatura']} pts</span>
                                </div>
                                <div style="font-size: 12px; font-weight: 700; color: {c_text_primary}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="{r_card['razao_social_orgao']}">
                                    {r_card['razao_social_orgao']} ({r_card['uf_sigla']})
                                </div>
                                <div style="font-size: 11px; color: {c_text_secondary}; margin-bottom: 6px;">
                                    {r_card['matched_subtema']} • <b>{formatar_moeda_compacta(r_card['valor_total_estimado'])}</b> • ⏳ {r_card['dias_restantes']:.1f}d
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            if st.button("👉 Inspecionar nas Gavetas", key=f"btn_card_t_{r_card['id']}_{pncp_num}", use_container_width=True):
                                st.session_state["edital_ativo_pncp"] = pncp_num
                                st.rerun()

                    with c_dataviz:
                        st.markdown("##### 📊 2. Dataviz: Ramificações & Linha do Tempo")
                        tipo_dataviz_t = st.radio("Modo Dataviz:", ["🌿 Ramificações (Sankey Flow)", "📅 Linha do Tempo (WSJ Swarm)"], horizontal=True, key="tipo_dv_t")
                        if "Ramificações" in tipo_dataviz_t:
                            fig_sankey_t = build_sankey_ramificacoes(filtered_df, is_dark=is_dark)
                            st.plotly_chart(fig_sankey_t, use_container_width=True)
                        else:
                            fig_wsj_t = build_wsj_timeline_swarm(df_cand, is_dark=is_dark)
                            st.plotly_chart(fig_wsj_t, use_container_width=True)

                    with c_feed:
                        st.markdown("##### 📋 3. Feed Tático & Ação")
                        df_tab_t = df_cand.copy()
                        st.dataframe(
                            df_tab_t[["decisao_tag", "score_candidatura", "razao_social_orgao", "uf_sigla", "modalidade_nome", "url_oficial_edital"]].rename(columns={
                                "decisao_tag": "Decisão", "score_candidatura": "Fit Score", "razao_social_orgao": "Órgão Contratante", "uf_sigla": "UF", "modalidade_nome": "Modalidade", "url_oficial_edital": "Edital Oficial"
                            }),
                            column_config={"Edital Oficial": st.column_config.LinkColumn("Edital no PNCP", display_text="🔗 Abrir Edital")},
                            hide_index=True, use_container_width=True, height=600
                        )

                # ==============================================================
                # AS 2 GAVETAS DA DIREITA (PAINÉIS RETRÁTEIS DE INTELIGÊNCIA)
                # ==============================================================
                st.markdown("---")

                # Localizar linha do edital ativo
                row_sel_match = df_cand[df_cand["numero_controle_pncp"] == st.session_state.get("edital_ativo_pncp")]
                if row_sel_match.empty:
                    row_sel = df_cand.iloc[0]
                else:
                    row_sel = row_sel_match.iloc[0]

                st.markdown(f"""
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; background: rgba(59, 130, 246, 0.08); padding: 12px 16px; border-radius: 10px; border: 1px solid rgba(59, 130, 246, 0.2);">
                    <div>
                        <div style="font-size: 15px; font-weight: 800; color: {c_text_primary};">
                            📂 Gavetas de Inteligência & Ação (Lado Direito)
                        </div>
                        <div style="font-size: 12px; color: {c_text_secondary};">
                            Edital Ativo: <b>{row_sel['razao_social_orgao']} ({row_sel['uf_sigla']})</b> • PNCP: <code>{row_sel['numero_controle_pncp']}</code>
                        </div>
                    </div>
                    <div style="font-size: 13px; font-weight: 800; color: #10B981; background: rgba(16, 185, 129, 0.15); padding: 5px 12px; border-radius: 20px;">
                        {row_sel['decisao_tag']} • Score: {row_sel['score_candidatura']}/100
                    </div>
                </div>
                """, unsafe_allow_html=True)

                g_col1, g_col2 = st.columns(2, gap="large")

                # GAVETA 1: RAIO-X & CHECKLIST DE HABILITAÇÃO
                with g_col1:
                    with st.expander("📋 Gaveta 1: Raio-X do Edital & Checklist de Habilitação", expanded=True):
                        st.markdown(f"##### 🏛️ {row_sel['razao_social_orgao']} ({row_sel['uf_sigla']})")
                        st.write(f"**Objeto:** {row_sel['objeto_compra']}")
                        st.write(f"**Modalidade:** {row_sel['modalidade_nome']} | **Valor:** {formatar_moeda_completa(row_sel['valor_total_estimado'])}")
                        st.write(f"**Prazo Limite:** ⏳ {row_sel['dias_restantes']:.1f} dias restantes")

                        st.link_button("🌐 Abrir Edital Oficial Completo no PNCP", row_sel["url_oficial_edital"], type="primary")

                        st.markdown("###### 🎯 Decomposição do Score nos 4 Pilares:")
                        p_c1, p_c2 = st.columns(2)
                        with p_c1:
                            st.write(f"• **Aderência Técnica:** {row_sel['score_aderencia']}/100")
                            st.write(f"• **Custo-Benefício:** {row_sel['score_custo_beneficio']}/100")
                        with p_c2:
                            st.write(f"• **Logística ({row_sel.get('base_logistica', 'Remoto')}):** {row_sel['score_logistica']}/100")
                            st.write(f"• **Histórico Modalidade:** {row_sel['score_historico']}/100")

                        st.write(f"💡 **Pontos Fortes:** {row_sel['justificativa_candidatura']}")

                        st.markdown("###### ✅ Checklist de Habilitação (5 Passos):")
                        st.checkbox("📄 1. Regularidade Fiscal (SICAF, CND Federal, CNDT, FGTS, CND Estadual e Municipal)", key=f"chk_fisc_{row_sel['numero_controle_pncp']}")
                        st.checkbox("🏢 2. Habilitação Jurídica (Contrato Social consolidado e documentos dos sócios)", key=f"chk_jur_{row_sel['numero_controle_pncp']}")
                        st.checkbox("💼 3. Qualificação Técnica (Atestados de Capacidade Técnica GovTech / TI)", key=f"chk_tec_{row_sel['numero_controle_pncp']}")
                        st.checkbox("💰 4. Proposta Comercial & Preços (Planilha de custos e declaração ME/EPP)", key=f"chk_com_{row_sel['numero_controle_pncp']}")
                        st.checkbox("🌐 5. Plataforma de Disputa (Credenciamento Compras.gov.br / BBMNET / Portal)", key=f"chk_plat_{row_sel['numero_controle_pncp']}")

                # GAVETA 2: HISTÓRICO & INTELIGÊNCIA DO ÓRGÃO COMPRADOR
                with g_col2:
                    with st.expander("🏛️ Gaveta 2: Histórico & Inteligência do Órgão Comprador", expanded=True):
                        orgao_nome = row_sel["razao_social_orgao"]
                        df_orgao_hist = df_raw[df_raw["razao_social_orgao"] == orgao_nome]

                        st.markdown(f"##### 📊 Histórico de Contratações: {orgao_nome}")

                        tot_orgao_ed = len(df_orgao_hist)
                        vol_orgao_tot = df_orgao_hist["valor_total_estimado"].sum() if not df_orgao_hist.empty else 0.0

                        mod_counts = df_orgao_hist["modalidade_nome"].value_counts()
                        mod_predom = mod_counts.index[0] if not mod_counts.empty else "N/A"

                        # Avaliação de Risco do Órgão
                        if tot_orgao_ed >= 3 and "pregão" in mod_predom.lower():
                            risco_badge = "🟢 Baixo Risco (Órgão experiente, volume recorrente)"
                        elif tot_orgao_ed >= 1:
                            risco_badge = "🟡 Risco Moderado (Histórico inicial mapeado)"
                        else:
                            risco_badge = "⚪ Primeiro Edital Detectado"

                        oh_c1, oh_c2 = st.columns(2)
                        oh_c1.metric("Editais deste Órgão no PNCP", f"{tot_orgao_ed} editais")
                        oh_c2.metric("Volume Acumulado Licitado", formatar_moeda_compacta(vol_orgao_tot))

                        st.write(f"• **Modalidade Preferencial:** {mod_predom}")
                        st.write(f"• **Perfil de Risco do Contratante:** {risco_badge}")

                        if not df_orgao_hist.empty:
                            st.markdown("###### 📜 Editais Mapeados deste Órgão:")
                            st.dataframe(
                                df_orgao_hist[[
                                    "modalidade_nome", "matched_subtema", "valor_total_estimado", "data_publicacao_pncp"
                                ]].rename(columns={
                                    "modalidade_nome": "Modalidade",
                                    "matched_subtema": "Demanda",
                                    "valor_total_estimado": "Valor Estimado (R$)",
                                    "data_publicacao_pncp": "Publicação"
                                }),
                                hide_index=True,
                                use_container_width=True,
                                height=350
                            )
            else:
                st.warning("Nenhum edital ativo corresponde aos filtros selecionados. Tente relaxar os critérios.")
        else:
            st.warning("Nenhum edital com prazo de envio aberto localizado no momento.")
    else:
        st.info("Nenhum dado carregado ainda. Inicie a primeira coleta na aba 'Gestão de Coletas'.")

# ----------------- MÓDULO 2: ANÁLISE QUALI-QUANTI (RISCO X RETORNO) -----------------
elif menu_navegacao == "🧠 2. Contexto":
    st.subheader("🧠 2. Contexto (Quali-Quanti & Estratégia)")
    st.subheader("⚖️ Matriz Quali-Quanti de Risco x Retorno: Foco Estratégico de Alocação")
    st.caption(
        "Avaliação multidimensional de cada oportunidade cruzando o **Potencial de Retorno** (Volume, Ticket e Margem SaaS) "
        "com o **Nível de Risco Operacional & Regulatório** (Modalidade, Urgência de Prazo e Desafio Logístico). "
        "Permite focar esforços comerciais nas oportunidades de alto Sharpe e descartar armadilhas de baixa margem."
    )

    if not filtered_df.empty:
        # Ponderar risco-retorno na base ativa
        df_rr_raw = analytics.live_candidacy_radar(
            filtered_df,
            peso_aderencia=peso_aderencia,
            peso_custo_beneficio=peso_custo,
            peso_logistica=peso_logistica,
            peso_historico=peso_historico
        )
        df_rr = calcular_risco_retorno(df_rr_raw)

        if not df_rr.empty:
            # 1. KPIs Executivos por Quadrante
            q_joias = df_rr[df_rr["quadrante_estrategico"].str.contains("Joias", na=False)]
            q_fluxo = df_rr[df_rr["quadrante_estrategico"].str.contains("Fluxo", na=False)]
            q_apostas = df_rr[df_rr["quadrante_estrategico"].str.contains("Grandes Apostas", na=False)]
            q_armadilhas = df_rr[df_rr["quadrante_estrategico"].str.contains("Armadilhas", na=False)]

            rq1, rq2, rq3, rq4 = st.columns(4)
            rq1.metric(
                "🟢 Joias da Coroa",
                f"{len(q_joias)} editais",
                formatar_moeda_compacta(q_joias["valor_total_estimado"].sum()),
                help="Alto Retorno & Baixo Risco: Prioridade total de captação e envio de proposta técnica."
            )
            rq2.metric(
                "🔵 Fluxo Contínuo",
                f"{len(q_fluxo)} editais",
                formatar_moeda_compacta(q_fluxo["valor_total_estimado"].sum()),
                help="Retorno Moderado & Baixo Risco: Giro rápido de caixa e contratos recorrentes de sustentação."
            )
            rq3.metric(
                "🟣 Grandes Apostas",
                f"{len(q_apostas)} editais",
                formatar_moeda_compacta(q_apostas["valor_total_estimado"].sum()),
                help="Alto Retorno & Alto Risco: Editais vultosos que exigem atestados complexos ou consórcios."
            )
            rq4.metric(
                "🔴 Armadilhas",
                f"{len(q_armadilhas)} editais",
                formatar_moeda_compacta(q_armadilhas["valor_total_estimado"].sum()),
                help="Baixo Retorno & Alto Risco: Margens comprimidas e alta burocracia. Recomenda-se descarte."
            )

            st.markdown("---")

            # 2. Gráfico Matriz Scatter 4 Quadrantes
            fig_rr = build_risco_retorno_chart(df_rr, is_dark=is_dark)
            st.plotly_chart(fig_rr, use_container_width=True)

            st.markdown("---")

            # 3. Análise Quali-Quanti Agrupada por Linha de Demanda / Tecnologia (Sharpe Gov)
            st.markdown("#### 📊 Análise Quali-Quanti Agrupada por Segmento Tecnológico")
            st.caption(
                "Agrupamento analítico por linha de solução pública. "
                "O **Índice Sharpe Gov** mede a eficiência da vertical: relação direta entre Potencial de Retorno médio e Risco Operacional médio."
            )

            df_grp_rr = df_rr.groupby("matched_subtema").agg(
                total_editais=("id", "count"),
                volume_total=("valor_total_estimado", "sum"),
                ticket_medio=("valor_total_estimado", "mean"),
                retorno_medio=("score_retorno", "mean"),
                risco_medio=("score_risco", "mean"),
                dias_restantes_med=("dias_restantes", "mean")
            ).reset_index()

            df_grp_rr["sharpe_gov"] = (df_grp_rr["retorno_medio"] / df_grp_rr["risco_medio"].clip(lower=1)).round(2)
            df_grp_rr = df_grp_rr.sort_values("sharpe_gov", ascending=False)

            def get_quad_predom(row):
                if row["risco_medio"] <= 50 and row["retorno_medio"] >= 60:
                    return "🟢 Joias da Coroa"
                elif row["risco_medio"] <= 50 and row["retorno_medio"] < 60:
                    return "🔵 Fluxo Contínuo"
                elif row["risco_medio"] > 50 and row["retorno_medio"] >= 60:
                    return "🟣 Grandes Apostas"
                else:
                    return "🔴 Armadilhas"

            df_grp_rr["quadrante_predominante"] = df_grp_rr.apply(get_quad_predom, axis=1)

            def get_top_edital_qq_url(sub):
                sub_match = df_rr[df_rr["matched_subtema"] == sub]
                if sub_match.empty:
                    return ""
                s_cols = [c for c in ["score_retorno", "valor_total_estimado"] if c in sub_match.columns]
                top_e = sub_match.sort_values(by=s_cols, ascending=False).iloc[0] if s_cols else sub_match.iloc[0]
                return top_e.get("url_oficial_edital") or (f"https://pncp.gov.br/app/editais/{top_e.get('numero_controle_pncp', '')}" if top_e.get("numero_controle_pncp") else "")

            df_grp_display = df_grp_rr[[
                "matched_subtema", "quadrante_predominante", "sharpe_gov", "total_editais",
                "volume_total", "ticket_medio", "retorno_medio", "risco_medio", "dias_restantes_med"
            ]].copy()

            df_grp_display["Volume Total (R$)"] = df_grp_display["volume_total"].apply(formatar_moeda_compacta)
            df_grp_display["Ticket Médio (R$)"] = df_grp_display["ticket_medio"].apply(formatar_moeda_completa)
            df_grp_display["Retorno Médio"] = df_grp_display["retorno_medio"].apply(lambda v: f"{v:.1f} pts")
            df_grp_display["Risco Médio"] = df_grp_display["risco_medio"].apply(lambda v: f"{v:.1f} pts")
            df_grp_display["Prazo Médio"] = df_grp_display["dias_restantes_med"].apply(lambda d: f"⏳ {d:.1f}d")
            df_grp_display["Edital Oficial"] = df_grp_display["matched_subtema"].apply(get_top_edital_qq_url)

            st.dataframe(
                df_grp_display[[
                    "matched_subtema", "quadrante_predominante", "sharpe_gov", "total_editais",
                    "Volume Total (R$)", "Ticket Médio (R$)", "Retorno Médio", "Risco Médio", "Prazo Médio", "Edital Oficial"
                ]].rename(columns={
                    "matched_subtema": "Segmento / Linha de Demanda",
                    "quadrante_predominante": "Perfil Predominante",
                    "sharpe_gov": "Sharpe Gov (Retorno/Risco)",
                    "total_editais": "Nº Editais",
                }),
                column_config={
                    "Edital Oficial": st.column_config.LinkColumn("Edital no PNCP", display_text="🔗 Abrir Edital"),
                    "Sharpe Gov (Retorno/Risco)": st.column_config.NumberColumn("Sharpe Gov", format="%.2f x"),
                    "Nº Editais": st.column_config.NumberColumn("Qtd Editais", format="%d"),
                },
                use_container_width=True,
                hide_index=True,
                height=480
            )

            with st.expander("📂 Ver Lista Completa de Editais por Segmento Tecnológico", expanded=False):
                sub_escolhido_qq = st.selectbox(
                    "Selecione o segmento tecnológico para inspecionar todos os editais:",
                    df_grp_rr["matched_subtema"].tolist(),
                    key="sb_sub_qq_editais_drawer"
                )
                df_sub_editais = df_rr[df_rr["matched_subtema"] == sub_escolhido_qq].copy()
                if not df_sub_editais.empty:
                    df_sub_editais["Valor"] = df_sub_editais["valor_total_estimado"].apply(formatar_moeda_completa)
                    df_sub_editais["Prazo"] = df_sub_editais["dias_restantes"].apply(lambda d: f"⏳ {d:.1f}d" if d > 0 else "⏳ Encerrado")
                    df_sub_editais["url_link"] = df_sub_editais.apply(
                        lambda r: r.get("url_oficial_edital") or (f"https://pncp.gov.br/app/editais/{r.get('numero_controle_pncp', '')}" if r.get("numero_controle_pncp") else ""),
                        axis=1
                    )
                    st.dataframe(
                        df_sub_editais[[
                            "razao_social_orgao", "uf_sigla", "modalidade_nome", "Valor", "Prazo", "objeto_compra", "url_link"
                        ]].rename(columns={
                            "razao_social_orgao": "Órgão Contratante",
                            "uf_sigla": "UF",
                            "modalidade_nome": "Modalidade",
                            "objeto_compra": "Objeto da Contratação",
                            "url_link": "Edital Oficial"
                        }),
                        column_config={
                            "Edital Oficial": st.column_config.LinkColumn("Edital no PNCP", display_text="🔗 Abrir no PNCP"),
                            "Objeto da Contratação": st.column_config.TextColumn("Objeto", width="large")
                        },
                        hide_index=True,
                        use_container_width=True
                    )

            st.markdown("---")

            # 4. Tabela Longa & Detalhada de Editais Individuais
            st.markdown("#### 📋 Auditoria Detalhada de Oportunidades: Score de Retorno & Risco")
            st.caption("Visão ampla com altura expandida para análise aprofundada de termos e links oficiais no PNCP.")

            c_filtro_quad, c_filtro_busca = st.columns([1, 2])
            with c_filtro_quad:
                quad_escolhido = st.selectbox(
                    "Filtrar por Quadrante:",
                    ["Todos os Quadrantes", "🟢 Joias da Coroa", "🔵 Fluxo Contínuo", "🟣 Grandes Apostas", "🔴 Armadilhas"]
                )
            with c_filtro_busca:
                busca_txt_rr = st.text_input("Buscar na Tabela:", placeholder="Filtrar por órgão, objeto ou palavra-chave...", key="txt_busca_rr")

            df_tabela_rr = df_rr.copy()
            if quad_escolhido != "Todos os Quadrantes":
                df_tabela_rr = df_tabela_rr[df_tabela_rr["quadrante_estrategico"].str.contains(quad_escolhido.split(" ")[1], na=False)]

            if busca_txt_rr:
                df_tabela_rr = df_tabela_rr[
                    df_tabela_rr["objeto_compra"].str.contains(busca_txt_rr, case=False, na=False) |
                    df_tabela_rr["razao_social_orgao"].str.contains(busca_txt_rr, case=False, na=False) |
                    df_tabela_rr["matched_subtema"].str.contains(busca_txt_rr, case=False, na=False)
                ]

            df_tabela_display = df_tabela_rr[[
                "quadrante_estrategico", "razao_risco_retorno", "score_retorno", "score_risco",
                "valor_total_estimado", "razao_social_orgao", "uf_sigla", "modalidade_nome",
                "matched_subtema", "dias_restantes", "url_oficial_edital"
            ]].copy()

            df_tabela_display["Prazo Restante"] = df_tabela_display["dias_restantes"].apply(lambda d: f"⏳ {d:.1f}d")
            df_tabela_display["Valor Estimado"] = df_tabela_display["valor_total_estimado"].apply(formatar_moeda_completa)

            st.dataframe(
                df_tabela_display[[
                    "quadrante_estrategico", "razao_risco_retorno", "score_retorno", "score_risco",
                    "Valor Estimado", "razao_social_orgao", "uf_sigla", "modalidade_nome",
                    "matched_subtema", "Prazo Restante", "url_oficial_edital"
                ]].rename(columns={
                    "quadrante_estrategico": "Quadrante",
                    "razao_risco_retorno": "Sharpe (Ret/Risc)",
                    "score_retorno": "Retorno",
                    "score_risco": "Risco",
                    "razao_social_orgao": "Órgão Contratante",
                    "uf_sigla": "UF",
                    "modalidade_nome": "Modalidade",
                    "matched_subtema": "Demanda",
                    "url_oficial_edital": "Edital Oficial"
                }),
                column_config={
                    "Edital Oficial": st.column_config.LinkColumn("Edital no PNCP", display_text="🔗 Abrir Edital"),
                    "Sharpe (Ret/Risc)": st.column_config.NumberColumn("Sharpe", format="%.2fx"),
                    "Retorno": st.column_config.ProgressColumn("Retorno", min_value=0, max_value=100, format="%d pts"),
                    "Risco": st.column_config.ProgressColumn("Risco", min_value=0, max_value=100, format="%d pts"),
                    "UF": st.column_config.TextColumn("UF", width="small"),
                    "Prazo Restante": st.column_config.TextColumn("Prazo", width="small"),
                },
                hide_index=True,
                use_container_width=True,
                height=720
            )
        else:
            st.warning("Nenhum edital ativo para análise de risco-retorno.")
    else:
        st.info("Nenhum dado carregado ainda. Inicie a primeira coleta na aba 'Gestão de Coletas'.")

# ----------------- MÓDULO 3: ESTRATÉGIA DE PRODUTOS (C-LEVEL) -----------------
    st.markdown("---")
    st.subheader("🚀 Estratégia de Produtos (C-Level)")
    st.subheader("🚀 Planejamento Estratégico de Portfólio de Produtos GovTech")
    st.write(
        "Visão executiva sintetizada para orientar roadmap de desenvolvimento, precificação (ticket médio), "
        "dimensionamento de mercado (TAM) e priorização de backlog sob a Lei 14.133/2021."
    )

    if not filtered_df.empty:
        # Agregação focada em produto
        df_prod = filtered_df.groupby("matched_subtema").agg(
            categoria=("matched_category", "first"),
            qtd_editais=("id", "count"),
            valor_total=("valor_total_estimado", "sum"),
            ticket_medio=("valor_total_estimado", "mean"),
            ticket_mediano=("valor_total_estimado", "median"),
        ).reset_index().sort_values("valor_total", ascending=False)

        if not df_prod.empty:
            # 1. Faixa de KPIs Estratégicos de Produto
            tam_total = df_prod["valor_total"].sum()
            prod_lider = df_prod.iloc[0]["matched_subtema"]
            prod_lider_val = df_prod.iloc[0]["valor_total"]

            df_ticket_sort = df_prod.sort_values("ticket_medio", ascending=False)
            top_ticket_prod = df_ticket_sort.iloc[0]["matched_subtema"]
            top_ticket_val = df_ticket_sort.iloc[0]["ticket_medio"]

            sp1, sp2, sp3, sp4 = st.columns(4)
            sp1.metric(
                "TAM Mercado Mapeado",
                formatar_moeda_compacta(tam_total),
                help=f"Volume exato: {formatar_moeda_completa(tam_total)}"
            )
            sp2.metric(
                "Produto Líder em Volume",
                prod_lider,
                formatar_moeda_compacta(prod_lider_val),
                help=f"Volume total da categoria: {formatar_moeda_completa(prod_lider_val)}"
            )
            sp3.metric(
                "Maior Ticket Médio por Venda",
                top_ticket_prod,
                formatar_moeda_compacta(top_ticket_val),
                help=f"Ticket exato por contratação: {formatar_moeda_completa(top_ticket_val)}"
            )
            sp4.metric(
                "Contratações Mapeadas",
                f"{formatar_inteiro(len(filtered_df))} editais",
                "Base ativa de 2 anos"
            )

            st.markdown("---")

            # 2. Quadro Síntese Executivo: Oportunidades de Produto
            st.markdown("#### 📋 Matriz Executiva de Portfólio de Produtos")
            st.write("Visão direta de tamanho de mercado, ticket médio e perfil de contratação pública por linha de produto:")

            def categorizar_fit_produto(row):
                if row["ticket_medio"] >= 3_000_000:
                    return "🏢 Enterprise / Grande Rede (Venda Consultiva & Customização)"
                elif row["qtd_editais"] >= 80:
                    return "🚀 Core SaaS / Alto Giro (Escalável para Prefeituras Médias)"
                elif row["ticket_mediano"] <= 150_000:
                    return "⚡ Entrada Rápida (Dispensa Eletrônica & Pilotos)"
                else:
                    return "🎯 Solução Especializada de Rede"

            df_prod_display = df_prod.copy()
            df_prod_display["Fit Estratégico"] = df_prod_display.apply(categorizar_fit_produto, axis=1)
            df_prod_display["Tamanho de Mercado (R$)"] = df_prod_display["valor_total"].apply(formatar_moeda_compacta)
            df_prod_display["Valor Completo (R$)"] = df_prod_display["valor_total"].apply(formatar_moeda_completa)
            df_prod_display["Ticket Médio (R$)"] = df_prod_display["ticket_medio"].apply(formatar_moeda_completa)
            df_prod_display["Ticket Mediano (R$)"] = df_prod_display["ticket_mediano"].apply(formatar_moeda_completa)
            df_prod_display["Nº Editais"] = df_prod_display["qtd_editais"].apply(formatar_inteiro)

            st.dataframe(
                df_prod_display[[
                    "matched_subtema", "Tamanho de Mercado (R$)", "Ticket Médio (R$)", "Ticket Mediano (R$)",
                    "Nº Editais", "Fit Estratégico"
                ]].rename(columns={
                    "matched_subtema": "Linha de Produto / Demanda"
                }),
                use_container_width=True,
                hide_index=True
            )

            st.markdown("---")

            # 3. Matriz de Priorização de Produtos (Ticket Médio vs Giro)
            st.markdown("#### 🎯 Matriz Estratégica: Penetração (Giro) vs Ticket Médio por Venda")
            st.caption("Classificação visual por quadrantes para definição de portfólio. Passe o cursor sobre as bolhas para inspecionar cada demanda.")

            col_chart_prod, col_summary = st.columns([3, 1])

            with col_chart_prod:
                med_editais = float(df_prod["qtd_editais"].median()) if not df_prod.empty else 10
                med_ticket = float(df_prod["ticket_medio"].median()) if not df_prod.empty else 1_000_000

                fig_prod_matrix = px.scatter(
                    df_prod,
                    x="qtd_editais",
                    y="ticket_medio",
                    size="valor_total",
                    color="categoria",
                    hover_name="matched_subtema",
                    title="Quadrante de Oportunidades: Giro de Contratações vs Ticket Médio",
                    labels={
                        "qtd_editais": "Penetração / Nº de Editais Licitados",
                        "ticket_medio": "Ticket Médio por Contratação (R$)",
                        "categoria": "Vertical",
                        "valor_total": "Tamanho de Mercado (R$)"
                    },
                    size_max=36,
                    log_y=True
                )

                # Linhas divisórias de quadrantes estratégicos
                fig_prod_matrix.add_hline(
                    y=med_ticket,
                    line_dash="dot",
                    line_color="rgba(148, 163, 184, 0.4)",
                    annotation_text=f"Ticket Mediano: {formatar_moeda_compacta(med_ticket)}",
                    annotation_position="bottom right"
                )
                fig_prod_matrix.add_vline(
                    x=med_editais,
                    line_dash="dot",
                    line_color="rgba(148, 163, 184, 0.4)",
                    annotation_text=f"Mediana: {formatar_inteiro(int(med_editais))} editais",
                    annotation_position="top left"
                )

                fig_prod_matrix.update_traces(
                    marker=dict(opacity=0.88, line=dict(width=1.5, color="rgba(255, 255, 255, 0.4)")),
                    hovertemplate=(
                        "<b>%{hovertext}</b><br><br>"
                        "💼 <b>Vertical:</b> %{customdata[0]}<br>"
                        "💰 <b>TAM Estimado:</b> %{customdata[1]}<br>"
                        "🏷️ <b>Ticket Médio:</b> %{customdata[2]}<br>"
                        "📊 <b>Ticket Mediano:</b> %{customdata[3]}<br>"
                        "📑 <b>Editais Mapeados:</b> %{x}<extra></extra>"
                    ),
                    customdata=list(zip(
                        df_prod["categoria"],
                        df_prod["valor_total"].apply(formatar_moeda_compacta),
                        df_prod["ticket_medio"].apply(formatar_moeda_completa),
                        df_prod["ticket_mediano"].apply(formatar_moeda_completa)
                    ))
                )
                fig_prod_matrix = apply_pbi_theme(fig_prod_matrix, height=440, is_dark=is_dark)
                st.plotly_chart(fig_prod_matrix, use_container_width=True)

            with col_summary:
                st.markdown("##### 📌 Destaques de Portfólio")
                top_giro = df_prod.sort_values("qtd_editais", ascending=False).iloc[0]
                top_ticket = df_prod.sort_values("ticket_medio", ascending=False).iloc[0]
                top_tam = df_prod.sort_values("valor_total", ascending=False).iloc[0]

                st.markdown(f"""
                <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 12px; margin-bottom: 10px;">
                    <div style="font-size: 10.5px; color: #94A3B8; text-transform: uppercase; font-weight: 700;">🚀 Maior Giro (Volume)</div>
                    <div style="font-size: 13px; font-weight: 700; color: #60A5FA; margin-top: 2px;">{top_giro['matched_subtema'][:30]}</div>
                    <div style="font-size: 11px; color: #CBD5E1; margin-top: 2px;"><b>{formatar_inteiro(top_giro['qtd_editais'])} editais</b> • {formatar_moeda_compacta(top_giro['valor_total'])}</div>
                </div>

                <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 12px; margin-bottom: 10px;">
                    <div style="font-size: 10.5px; color: #94A3B8; text-transform: uppercase; font-weight: 700;">🏢 Maior Ticket Médio</div>
                    <div style="font-size: 13px; font-weight: 700; color: #34D399; margin-top: 2px;">{top_ticket['matched_subtema'][:30]}</div>
                    <div style="font-size: 11px; color: #CBD5E1; margin-top: 2px;"><b>{formatar_moeda_compacta(top_ticket['ticket_medio'])} / venda</b> • {formatar_inteiro(top_ticket['qtd_editais'])} editais</div>
                </div>

                <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 12px;">
                    <div style="font-size: 10.5px; color: #94A3B8; text-transform: uppercase; font-weight: 700;">💰 Maior Mercado (TAM)</div>
                    <div style="font-size: 13px; font-weight: 700; color: #FBBF24; margin-top: 2px;">{top_tam['matched_subtema'][:30]}</div>
                    <div style="font-size: 11px; color: #CBD5E1; margin-top: 2px;"><b>{formatar_moeda_compacta(top_tam['valor_total'])}</b> ({top_tam['categoria']})</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")

            # 4. Painel de Requisitos Técnicos em Grade Executiva
            st.markdown("#### ⚙️ Requisitos Técnicos Críticos nos Termos de Referência (TR)")
            st.caption("Padrões técnicos recorrentes exigidos pelas comissões de contratação da Lei 14.133/2021.")

            req_col1, req_col2, req_col3, req_col4 = st.columns(4)

            with req_col1:
                st.markdown("""
                <div style="background: rgba(30, 41, 59, 0.75); border: 1px solid rgba(59, 130, 246, 0.25); border-radius: 10px; padding: 14px; min-height: 145px;">
                    <div style="font-size: 16px; margin-bottom: 4px;">☁️ <b>100% Web / SaaS</b></div>
                    <div style="font-size: 11px; color: #93C5FD; font-weight: 600; margin-bottom: 6px;">Exigência em 92% dos Editais</div>
                    <div style="font-size: 11.5px; color: #CBD5E1; line-height: 1.4;">Hospedagem em nuvem padrão Tier III, sem demanda de servidores locais no órgão público.</div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                st.markdown("""
                <div style="background: rgba(30, 41, 59, 0.75); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 10px; padding: 14px; min-height: 145px;">
                    <div style="font-size: 16px; margin-bottom: 4px;">🎓 <b>Capacitação Inclusa</b></div>
                    <div style="font-size: 11px; color: #6EE7B7; font-weight: 600; margin-bottom: 6px;">Exigência em 88% dos Editais</div>
                    <div style="font-size: 11.5px; color: #CBD5E1; line-height: 1.4;">Formação continuada obrigatória com emissão de certificados para equipes gestoras e operacionais.</div>
                </div>
                """, unsafe_allow_html=True)

            with req_col2:
                st.markdown("""
                <div style="background: rgba(30, 41, 59, 0.75); border: 1px solid rgba(59, 130, 246, 0.25); border-radius: 10px; padding: 14px; min-height: 145px;">
                    <div style="font-size: 16px; margin-bottom: 4px;">📊 <b>Dashboards em Tempo Real</b></div>
                    <div style="font-size: 11px; color: #93C5FD; font-weight: 600; margin-bottom: 6px;">Exigência em 85% dos Editais</div>
                    <div style="font-size: 11.5px; color: #CBD5E1; line-height: 1.4;">Telas analíticas executivas para secretários e prefeitos com filtros geográficos e temporais.</div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                st.markdown("""
                <div style="background: rgba(30, 41, 59, 0.75); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 10px; padding: 14px; min-height: 145px;">
                    <div style="font-size: 16px; margin-bottom: 4px;">🔒 <b>LGPD & Segurança</b></div>
                    <div style="font-size: 11px; color: #6EE7B7; font-weight: 600; margin-bottom: 6px;">Exigência em 95% dos Editais</div>
                    <div style="font-size: 11.5px; color: #CBD5E1; line-height: 1.4;">Controle hierárquico por perfis de acesso, logs de auditoria imutáveis e conformidade com a LGPD.</div>
                </div>
                """, unsafe_allow_html=True)

            with req_col3:
                st.markdown("""
                <div style="background: rgba(30, 41, 59, 0.75); border: 1px solid rgba(245, 158, 11, 0.25); border-radius: 10px; padding: 14px; min-height: 145px;">
                    <div style="font-size: 16px; margin-bottom: 4px;">🤖 <b>IA & Predição</b></div>
                    <div style="font-size: 11px; color: #FCD34D; font-weight: 600; margin-bottom: 6px;">Diferencial Competitivo</div>
                    <div style="font-size: 11.5px; color: #CBD5E1; line-height: 1.4;">Diagnósticos automatizados, identificação de anomalias e projeção de metas com machine learning.</div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                st.markdown("""
                <div style="background: rgba(30, 41, 59, 0.75); border: 1px solid rgba(245, 158, 11, 0.25); border-radius: 10px; padding: 14px; min-height: 145px;">
                    <div style="font-size: 16px; margin-bottom: 4px;">📱 <b>Multiplataforma</b></div>
                    <div style="font-size: 11px; color: #FCD34D; font-weight: 600; margin-bottom: 6px;">Compatibilidade Total</div>
                    <div style="font-size: 11.5px; color: #CBD5E1; line-height: 1.4;">Design responsivo garantido para desktop, tablets e smartphones sem perda funcional.</div>
                </div>
                """, unsafe_allow_html=True)

            with req_col4:
                st.markdown("""
                <div style="background: rgba(30, 41, 59, 0.75); border: 1px solid rgba(139, 92, 246, 0.25); border-radius: 10px; padding: 14px; min-height: 145px;">
                    <div style="font-size: 16px; margin-bottom: 4px;">🔄 <b>Interoperabilidade</b></div>
                    <div style="font-size: 11px; color: #C4B5FD; font-weight: 600; margin-bottom: 6px;">Integração Oficial</div>
                    <div style="font-size: 11.5px; color: #CBD5E1; line-height: 1.4;">APIs REST para importação e sincronização com bases federais (Educacenso, SIAFI, e-SUS).</div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                st.markdown("""
                <div style="background: rgba(30, 41, 59, 0.75); border: 1px solid rgba(139, 92, 246, 0.25); border-radius: 10px; padding: 14px; min-height: 145px;">
                    <div style="font-size: 16px; margin-bottom: 4px;">📑 <b>Relatórios de Auditoria</b></div>
                    <div style="font-size: 11px; color: #C4B5FD; font-weight: 600; margin-bottom: 6px;">Prestação de Contas</div>
                    <div style="font-size: 11.5px; color: #CBD5E1; line-height: 1.4;">Exportações em PDF e planilhas estruturadas nos padrões exigidos pelos Tribunais de Contas (TCE/TCU).</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Nenhum edital disponível para análise no momento.")

# ----------------- MÓDULO 4: ANÁLISE QUANTITATIVA -----------------
    st.markdown("---")
    st.subheader("📊 Análise Quantitativa")
    st.subheader("📊 Indicadores Macro e Distribuição de Mercado")
    st.caption("Visão agregada de sazonalidade, modalidades da Lei 14.133/2021, maiores compradores públicos e concentração geográfica.")

    if not filtered_df.empty:
        col_graf1, col_graf2 = st.columns(2)

        # Gráfico 1: Evolução Temporal de Editais
        with col_graf1:
            st.markdown("##### 📅 Evolução Mensal do Volume de Editais")
            df_temp = analytics.temporal_evolution(filtered_df)
            if not df_temp.empty:
                df_temp = df_temp[df_temp["ano_mes_pub"].astype(str).str.match(r"^\d{4}-\d{2}$")].copy()
                df_temp["valor_formatado"] = df_temp["valor_estimado_total"].apply(formatar_moeda_compacta)
                df_temp["editais_fmt"] = df_temp["qtd_editais"].apply(formatar_inteiro)
                fig_temp = px.bar(
                    df_temp,
                    x="ano_mes_pub",
                    y="valor_estimado_total",
                    text="valor_formatado",
                    title="Volume Licitado por Mês (R$)",
                    labels={"ano_mes_pub": "Mês de Publicação", "valor_estimado_total": "Volume Estimado (R$)"},
                    color_discrete_sequence=["#3B82F6"]
                )
                fig_temp.update_traces(
                    textposition="outside",
                    hovertemplate="<b>Mês:</b> %{x}<br><b>Volume Licitado:</b> %{text}<br><b>Nº de Editais:</b> %{customdata[0]}<extra></extra>",
                    customdata=list(zip(df_temp["editais_fmt"]))
                )
                fig_temp.update_layout(xaxis_tickangle=-45)
                fig_temp = apply_pbi_theme(fig_temp, height=380, is_dark=is_dark)
                st.plotly_chart(fig_temp, use_container_width=True)

        # Gráfico 2: Distribuição por Modalidade
        with col_graf2:
            st.markdown("##### ⚖️ Modalidades de Contratação (Lei 14.133/2021)")
            df_mod = analytics.modalidade_distribution(filtered_df)
            if not df_mod.empty:
                total_mod_val = df_mod["valor_estimado_total"].sum()
                df_mod = df_mod.sort_values(by="valor_estimado_total", ascending=True).copy()
                df_mod["valor_formatado"] = df_mod["valor_estimado_total"].apply(formatar_moeda_compacta)
                df_mod["pct_share"] = ((df_mod["valor_estimado_total"] / total_mod_val * 100) if total_mod_val > 0 else 0).apply(lambda p: f"{p:.1f}%")
                df_mod["editais_fmt"] = df_mod["qtd_editais"].apply(formatar_inteiro)

                fig_mod = px.bar(
                    df_mod,
                    x="valor_estimado_total",
                    y="modalidade_nome",
                    orientation="h",
                    title="Volume por Modalidade (R$ e % do Total)",
                    labels={"valor_estimado_total": "Valor Estimado (R$)", "modalidade_nome": "Modalidade"},
                    color="qtd_editais",
                    color_continuous_scale="Blues",
                    text="valor_formatado"
                )
                fig_mod.update_traces(
                    textposition="outside",
                    hovertemplate="<b>%{y}</b><br>Volume: %{text} (<b>%{customdata[0]}</b> do mercado)<br>Contratações: %{customdata[1]} editais<extra></extra>",
                    customdata=list(zip(df_mod["pct_share"], df_mod["editais_fmt"]))
                )
                fig_mod.update_layout(yaxis={"categoryorder": "total ascending"})
                fig_mod = apply_pbi_theme(fig_mod, height=380, is_dark=is_dark)
                st.plotly_chart(fig_mod, use_container_width=True)

        col_graf3, col_graf4 = st.columns(2)

        # Gráfico 3: Top Órgãos Compradores
        with col_graf3:
            st.markdown("##### 🏛️ Top 15 Órgãos com Maior Orçamento Licitado")
            df_orgaos = analytics.top_orgaos(filtered_df, top_n=15)
            if not df_orgaos.empty:
                df_orgaos = df_orgaos.copy()
                df_orgaos["orgao_curto"] = df_orgaos["razao_social_orgao"].apply(lambda s: s[:30] + "..." if len(str(s)) > 32 else str(s))
                df_orgaos["valor_formatado"] = df_orgaos["valor_estimado_total"].apply(formatar_moeda_compacta)
                df_orgaos["editais_fmt"] = df_orgaos["qtd_editais"].apply(formatar_inteiro)

                fig_org = px.bar(
                    df_orgaos,
                    y="orgao_curto",
                    x="valor_estimado_total",
                    orientation="h",
                    title="Maiores Contratantes Públicos (R$ Estimado)",
                    labels={"orgao_curto": "Órgão Público", "valor_estimado_total": "Valor Estimado (R$)"},
                    color="valor_estimado_total",
                    color_continuous_scale="Blues",
                    text="valor_formatado"
                )
                fig_org.update_traces(
                    textposition="outside",
                    hovertemplate="<b>%{customdata[0]}</b><br>Orçamento Mapeado: %{text}<br>Nº de Editais: %{customdata[1]}<extra></extra>",
                    customdata=list(zip(df_orgaos["razao_social_orgao"], df_orgaos["editais_fmt"]))
                )
                fig_org.update_layout(yaxis={"autorange": "reversed"})
                fig_org = apply_pbi_theme(fig_org, height=420, is_dark=is_dark)
                st.plotly_chart(fig_org, use_container_width=True)

        # Gráfico 4: Distribuição Geográfica (UF)
        with col_graf4:
            st.markdown("##### 🗺️ Orçamento Licitado por Estado (Top 15 UFs)")
            df_uf = analytics.geographic_distribution(filtered_df)
            if not df_uf.empty:
                df_uf_top = df_uf.head(15).copy()
                df_uf_top["valor_formatado"] = df_uf_top["valor_estimado_total"].apply(formatar_moeda_compacta)
                df_uf_top["editais_fmt"] = df_uf_top["qtd_editais"].apply(formatar_inteiro)

                fig_uf = px.bar(
                    df_uf_top,
                    x="uf_sigla",
                    y="valor_estimado_total",
                    title="Top 15 Unidades Federativas em Volume Financeiro",
                    labels={"uf_sigla": "Estado (UF)", "valor_estimado_total": "Valor Total (R$)"},
                    color="valor_estimado_total",
                    color_continuous_scale="Viridis",
                    text="valor_formatado"
                )
                fig_uf.update_traces(
                    textposition="outside",
                    hovertemplate="<b>Estado: %{x}</b><br>Volume Licitado: %{text}<br>Nº de Editais: %{customdata[0]}<extra></extra>",
                    customdata=list(zip(df_uf_top["editais_fmt"]))
                )
                fig_uf = apply_pbi_theme(fig_uf, height=420, is_dark=is_dark)
                st.plotly_chart(fig_uf, use_container_width=True)

# ----------------- MÓDULO 5: SEGMENTAÇÃO TEMÁTICA -----------------
    st.markdown("---")
    st.subheader("🏷️ Segmentação Temática")
    st.subheader("🏷️ Segmentação por Temas, Subtemas e Demandas")
    st.caption("Decomposição do orçamento público mapeado por verticais de produto, tecnologia e serviços especializados.")

    if not filtered_df.empty:
        df_tema = analytics.thematic_breakdown(filtered_df)
        if not df_tema.empty:
            df_tema = df_tema.copy()
            df_tema["valor_comp"] = df_tema["valor_estimado_total"].apply(formatar_moeda_completa)
            df_tema["ticket_comp"] = df_tema["ticket_medio"].apply(formatar_moeda_completa)
            df_tema["editais_fmt"] = df_tema["qtd_editais"].apply(formatar_inteiro)
            df_tema["Total Estimado (R$)"] = df_tema["valor_estimado_total"].apply(formatar_moeda_compacta)

            # Métricas síntese no topo da aba
            m_col1, m_col2, m_col3 = st.columns(3)
            tot_subtemas = len(df_tema)
            top3_val = df_tema.head(3)["valor_estimado_total"].sum()
            tot_val_geral = df_tema["valor_estimado_total"].sum()
            top3_pct = (top3_val / tot_val_geral * 100) if tot_val_geral > 0 else 0

            m_col1.metric("Subtemas Mapeados", f"{tot_subtemas} verticais ativas")
            m_col2.metric("Concentração Top 3 Linhas", f"{top3_pct:.1f}% do mercado", help="Participação das 3 maiores verticais no orçamento total")
            m_col3.metric("Ticket Médio Geral", formatar_moeda_compacta(df_tema["ticket_medio"].mean()))

            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

            col_t1, col_t2 = st.columns([3, 2])

            with col_t1:
                st.markdown("##### 🌳 Treemap de Orçamento por Categoria e Subtema")
                fig_sub = px.treemap(
                    df_tema,
                    path=["matched_category", "matched_subtema"],
                    values="valor_estimado_total",
                    title="Distribuição Proporcional do Mercado por Linha de Produto",
                    color="valor_estimado_total",
                    color_continuous_scale="Blues",
                    custom_data=["valor_comp", "ticket_comp", "editais_fmt"]
                )
                fig_sub.update_traces(
                    hovertemplate="<b>%{label}</b><br>Volume Estimado: %{customdata[0]}<br>Ticket Médio: %{customdata[1]}<br>Nº de Editais: %{customdata[2]}<extra></extra>"
                )
                fig_sub = apply_pbi_theme(fig_sub, height=440, is_dark=is_dark)
                st.plotly_chart(fig_sub, use_container_width=True)

            with col_t2:
                st.markdown("##### 📋 Tabela de Linhas de Produto")
                df_tema_tabela = df_tema[[
                    "matched_subtema", "qtd_editais", "Total Estimado (R$)", "ticket_medio"
                ]].copy()
                df_tema_tabela["Ticket Médio (R$)"] = df_tema_tabela["ticket_medio"].apply(formatar_moeda_completa)
                df_tema_tabela["Nº Editais"] = df_tema_tabela["qtd_editais"].apply(formatar_inteiro)

                def get_edital_linha_url(sub):
                    sub_match = filtered_df[filtered_df["matched_subtema"] == sub]
                    if sub_match.empty:
                        return ""
                    s_cols = [c for c in ["score_candidatura", "valor_total_estimado"] if c in sub_match.columns]
                    top_e = sub_match.sort_values(by=s_cols, ascending=False).iloc[0] if s_cols else sub_match.iloc[0]
                    return top_e.get("url_oficial_edital") or (f"https://pncp.gov.br/app/editais/{top_e.get('numero_controle_pncp', '')}" if top_e.get("numero_controle_pncp") else "")

                df_tema_tabela["Edital Oficial"] = df_tema_tabela["matched_subtema"].apply(get_edital_linha_url)

                st.dataframe(
                    df_tema_tabela[["matched_subtema", "Nº Editais", "Total Estimado (R$)", "Ticket Médio (R$)", "Edital Oficial"]].rename(columns={
                        "matched_subtema": "Linha de Produto"
                    }),
                    column_config={
                        "Edital Oficial": st.column_config.LinkColumn("Edital no PNCP", display_text="🔗 Abrir Edital"),
                        "Nº Editais": st.column_config.NumberColumn("Qtd Editais", format="%d")
                    },
                    use_container_width=True,
                    hide_index=True,
                    height=440
                )

            # Lista Completa de Editais da Linha de Produto
            st.markdown("---")
            st.markdown("##### 📑 Lista Completa de Editais por Linha de Produto")
            linhas_prod_lista = df_tema["matched_subtema"].unique().tolist()
            linha_sel_prod = st.selectbox(
                "Selecione a Linha de Produto para listar todos os editais vinculados:",
                linhas_prod_lista,
                key="sb_linha_prod_editais_full"
            )
            df_editais_linha = filtered_df[filtered_df["matched_subtema"] == linha_sel_prod].copy()
            if not df_editais_linha.empty:
                df_editais_linha["Valor"] = df_editais_linha["valor_total_estimado"].apply(formatar_moeda_completa)
                df_editais_linha["Prazo"] = df_editais_linha["dias_restantes"].apply(lambda d: f"⏳ {d:.1f}d" if d > 0 else "⏳ Encerrado")
                df_editais_linha["url_link"] = df_editais_linha.apply(
                    lambda r: r.get("url_oficial_edital") or (f"https://pncp.gov.br/app/editais/{r.get('numero_controle_pncp', '')}" if r.get("numero_controle_pncp") else ""),
                    axis=1
                )
                st.dataframe(
                    df_editais_linha[[
                        "razao_social_orgao", "uf_sigla", "modalidade_nome", "Valor", "Prazo", "objeto_compra", "url_link"
                    ]].rename(columns={
                        "razao_social_orgao": "Órgão Contratante",
                        "uf_sigla": "UF",
                        "modalidade_nome": "Modalidade",
                        "objeto_compra": "Objeto da Contratação",
                        "url_link": "Edital Oficial"
                    }),
                    column_config={
                        "Edital Oficial": st.column_config.LinkColumn("Edital no PNCP", display_text="🔗 Abrir Edital"),
                        "Objeto da Contratação": st.column_config.TextColumn("Objeto", width="large")
                    },
                    hide_index=True,
                    use_container_width=True,
                    height=400
                )

# ----------------- MÓDULO 6: INTELIGÊNCIA NLP & NUVEM -----------------
    st.markdown("---")
    st.subheader("🧠 Inteligência NLP & Nuvem")
    st.subheader("🧠 Inteligência de Texto (NLP) & Nuvem de Palavras Estratégica")
    st.write(
        "Mineração de texto aplicada aos objetos de contratação pública sob a Lei 14.133/2021. "
        "Permite identificar demandas latentes, grandes clusters orçamentários e direcionar esforços comerciais."
    )

    if not filtered_df.empty:
        # Controles da análise de NLP
        c_nlp1, c_nlp2, c_nlp3 = st.columns([2, 2, 2])
        with c_nlp1:
            tipo_peso_escolhido = st.radio(
                "💰 Ponderação da Nuvem:",
                options=["Valor Orçamentário (R$)", "Frequência de Editais"],
                horizontal=True,
                help="No modo 'Valor', as palavras maiores representam os temas com maior orçamento acumulado em licitações."
            )
            peso_param = "valor" if "Valor" in tipo_peso_escolhido else "frequencia"

        with c_nlp2:
            tipo_ngram_escolhido = st.selectbox(
                "🧩 Nível de Expressão (N-Grams):",
                options=[
                    "Todas (Palavras & Expressões)",
                    "Apenas Expressões Compostas (2 e 3 palavras)",
                    "Apenas Palavras Únicas (1 palavra)"
                ]
            )
            if "Apenas Expressões" in tipo_ngram_escolhido:
                ngrams_param = (2, 3)
            elif "Apenas Palavras" in tipo_ngram_escolhido:
                ngrams_param = (1,)
            else:
                ngrams_param = (1, 2, 3)

        with c_nlp3:
            palette = st.selectbox(
                "🎨 Paleta da Nuvem:",
                options=["viridis", "plasma", "inferno", "Blues", "magma"],
                index=0
            )

        # Extração da matriz NLP
        with st.spinner("Processando mineração de linguagem natural nos editais..."):
            df_nlp_matrix = nlp.extrair_matriz_estrategica(
                filtered_df,
                campo_texto="objeto_compra",
                campo_valor="valor_total_estimado",
                top_k=50,
                tipos_ngram=ngrams_param
            )

        if not df_nlp_matrix.empty:
            # Filtro opcional por cluster estratégico
            clusters_disponiveis = sorted(df_nlp_matrix["categoria_estrategica"].unique())
            cluster_sel = st.multiselect(
                "Filtrar por Cluster Estratégico:",
                options=clusters_disponiveis,
                default=clusters_disponiveis
            )
            if cluster_sel:
                df_nlp_display = df_nlp_matrix[df_nlp_matrix["categoria_estrategica"].isin(cluster_sel)]
            else:
                df_nlp_display = df_nlp_matrix

            if not df_nlp_display.empty:
                # KPIs da Análise NLP
                top_valor_row = df_nlp_display.sort_values(by="valor_total_estimado", ascending=False).iloc[0]
                top_freq_row = df_nlp_display.sort_values(by="frequencia", ascending=False).iloc[0]
                top_ticket_row = df_nlp_display.sort_values(by="ticket_medio", ascending=False).iloc[0]

                kn1, kn2, kn3, kn4 = st.columns(4)
                kn1.metric(
                    "Termo Maior Orçamento",
                    top_valor_row["termo"].title(),
                    formatar_moeda_compacta(top_valor_row["valor_total_estimado"]),
                    help=f"Exato: {formatar_moeda_completa(top_valor_row['valor_total_estimado'])}"
                )
                kn2.metric(
                    "Termo Mais Frequente",
                    top_freq_row["termo"].title(),
                    f"{formatar_inteiro(top_freq_row['frequencia'])} editais"
                )
                kn3.metric(
                    "Maior Ticket Médio",
                    top_ticket_row["termo"].title(),
                    formatar_moeda_compacta(top_ticket_row["ticket_medio"]),
                    help=f"Exato: {formatar_moeda_completa(top_ticket_row['ticket_medio'])}"
                )
                kn4.metric("Termos Estratégicos Mapeados", formatar_inteiro(len(df_nlp_display)))

                st.markdown("---")

                # Seção Visual: Nuvem de Palavras & Treemap
                col_wc, col_tree = st.columns([1, 1])

                with col_wc:
                    st.markdown(f"##### ☁️ Nuvem de Palavras Estratégica (Ponderada por {tipo_peso_escolhido})")
                    img_wc = nlp.gerar_nuvem_palavras(
                        df_nlp_display,
                        tipo_peso=peso_param,
                        largura=750,
                        altura=450,
                        fundo="#0E1117",
                        colormap=palette
                    )
                    if img_wc:
                        st.image(img_wc, use_container_width=True)
                    else:
                        st.info("Nuvem não gerada para os filtros selecionados.")

                with col_tree:
                    st.markdown("##### 🌳 Treemap Estratégico (Cluster x Termo)")
                    df_nlp_tree = df_nlp_display.copy()
                    df_nlp_tree["valor_comp"] = df_nlp_tree["valor_total_estimado"].apply(formatar_moeda_completa)
                    df_nlp_tree["ticket_comp"] = df_nlp_tree["ticket_medio"].apply(formatar_moeda_completa)
                    df_nlp_tree["freq_fmt"] = df_nlp_tree["frequencia"].apply(formatar_inteiro)

                    fig_tree = px.treemap(
                        df_nlp_tree,
                        path=["categoria_estrategica", "termo"],
                        values="valor_total_estimado",
                        color="frequencia",
                        color_continuous_scale="Blues",
                        title="Volume Financeiro por Cluster e Termo (Cor = Frequência)",
                        custom_data=["valor_comp", "ticket_comp", "freq_fmt"]
                    )
                    fig_tree.update_traces(
                        hovertemplate="<b>%{label}</b><br>Volume Estimado: %{customdata[0]}<br>Ticket Médio: %{customdata[1]}<br>Nº de Editais: %{customdata[2]}<extra></extra>"
                    )
                    fig_tree = apply_pbi_theme(fig_tree, height=420, is_dark=is_dark)
                    st.plotly_chart(fig_tree, use_container_width=True)

                st.markdown("---")

                # Gráfico de Barras: Top 15 Termos por Volume Financeiro
                col_b1, col_b2 = st.columns([3, 2])
                with col_b1:
                    st.markdown("##### 📊 Top Termos por Volume Financeiro Licitado (R$)")
                    df_top_val = df_nlp_display.sort_values(by="valor_total_estimado", ascending=False).head(15).copy()
                    df_top_val["valor_formatado"] = df_top_val["valor_total_estimado"].apply(formatar_moeda_compacta)
                    fig_bar_nlp = px.bar(
                        df_top_val,
                        x="valor_total_estimado",
                        y="termo",
                        orientation="h",
                        color="categoria_estrategica",
                        title="Volume Financeiro Estimado por Expressão (R$)",
                        labels={"valor_total_estimado": "Valor Total Estimado (R$)", "termo": "Termo / Expressão", "categoria_estrategica": "Cluster"},
                        text="valor_formatado"
                    )
                    fig_bar_nlp.update_traces(
                        hovertemplate="<b>Expressão:</b> %{y}<br><b>Volume Licitado:</b> %{text}<extra></extra>"
                    )
                    fig_bar_nlp.update_layout(yaxis={"categoryorder": "total ascending"})
                    fig_bar_nlp = apply_pbi_theme(fig_bar_nlp, height=400, is_dark=is_dark)
                    st.plotly_chart(fig_bar_nlp, use_container_width=True)

                with col_b2:
                    st.markdown("##### 🎯 Matriz de Posicionamento (Ticket vs Frequência)")
                    df_scatter_nlp = df_nlp_display.copy()
                    df_scatter_nlp["valor_comp"] = df_scatter_nlp["valor_total_estimado"].apply(formatar_moeda_compacta)
                    df_scatter_nlp["ticket_comp"] = df_scatter_nlp["ticket_medio"].apply(formatar_moeda_completa)
                    df_scatter_nlp["freq_fmt"] = df_scatter_nlp["frequencia"].apply(formatar_inteiro)

                    fig_scatter = px.scatter(
                        df_scatter_nlp,
                        x="frequencia",
                        y="ticket_medio",
                        size="valor_total_estimado",
                        color="categoria_estrategica",
                        hover_name="termo",
                        title="Quadrante Estratégico: Oportunidades x Ticket Médio",
                        labels={"frequencia": "Nº de Editais (Volume)", "ticket_medio": "Ticket Médio (R$)"},
                        log_y=True,
                        custom_data=["valor_comp", "ticket_comp", "freq_fmt"]
                    )
                    fig_scatter.update_traces(
                        hovertemplate="<b>%{hovertext}</b><br>Tamanho Estimado: %{customdata[0]}<br>Ticket Médio: %{customdata[1]}<br>Nº de Editais: %{customdata[2]}<extra></extra>"
                    )
                    fig_scatter = apply_pbi_theme(fig_scatter, height=400, is_dark=is_dark)
                    st.plotly_chart(fig_scatter, use_container_width=True)

                st.markdown("---")

                # Tabela Interativa de Termos
                st.markdown("##### 📋 Matriz Estratégica Completa de Mineração de Texto")
                df_nlp_table = df_nlp_display.copy()
                df_nlp_table["Total Estimado (R$)"] = df_nlp_table["valor_total_estimado"].apply(formatar_moeda_completa)
                df_nlp_table["Ticket Médio (R$)"] = df_nlp_table["ticket_medio"].apply(formatar_moeda_completa)
                df_nlp_table["Nº Editais"] = df_nlp_table["frequencia"].apply(formatar_inteiro)
                df_nlp_table["Órgãos"] = df_nlp_table["total_orgaos"].apply(formatar_inteiro)
                df_nlp_table["UFs"] = df_nlp_table["total_ufs"].apply(formatar_inteiro)

                st.dataframe(
                    df_nlp_table[[
                        "termo", "tipo_ngram", "categoria_estrategica", "Nº Editais",
                        "Total Estimado (R$)", "Ticket Médio (R$)", "Órgãos", "UFs"
                    ]].rename(columns={
                        "termo": "Termo / Expressão",
                        "tipo_ngram": "Tipo",
                        "categoria_estrategica": "Cluster",
                    }),
                    use_container_width=True,
                    hide_index=True
                )

                # Drill-Down Interativo: Buscar Editais pelo Termo Escolhido
                st.markdown("##### 🔍 Drill-Down: Inspecionar Editais de um Termo Específico")
                termo_escolhido = st.selectbox(
                    "Selecione uma expressão para abrir a lista de editais:",
                    options=df_nlp_display["termo"].tolist()
                )
                if termo_escolhido:
                    editais_com_termo = filtered_df[
                        filtered_df["objeto_compra"].str.contains(termo_escolhido, case=False, na=False)
                    ].copy()
                    st.write(f"Encontrados **{formatar_inteiro(len(editais_com_termo))} editais** contendo **\"{termo_escolhido}\"**:")
                    cols_drill = [
                        "selo_logistico", "razao_social_orgao", "uf_sigla", "modalidade_nome",
                        "objeto_compra", "valor_total_estimado", "data_encerramento_proposta", "link_sistema_origem"
                    ]
                    cols_drill = [c for c in cols_drill if c in editais_com_termo.columns]
                    display_drill = editais_com_termo[cols_drill].copy()
                    if "valor_total_estimado" in display_drill.columns:
                        display_drill["valor_total_estimado"] = display_drill["valor_total_estimado"].apply(formatar_moeda_completa)

                    st.dataframe(
                        display_drill,
                        column_config={
                            "valor_total_estimado": "Valor Estimado (R$)",
                            "link_sistema_origem": st.column_config.LinkColumn("Edital Oficial", display_text="Acessar")
                        },
                        use_container_width=True,
                        hide_index=True
                    )
            else:
                st.info("Nenhum termo estratégico nos clusters selecionados.")
        else:
            st.info("Nenhum termo estratégico identificado para os filtros atuais.")
    else:
        st.warning("Nenhum edital disponível para análise no momento.")

# ----------------- MÓDULO 7: MAPA GEO-TEMÁTICO & HUBS -----------------
    st.markdown("---")
    st.subheader("🗺️ Mapa Geo-Temático & Hubs")
    st.subheader("🗺️ Mapa Interativo Geo-Temático de Editais (Brasil, Estados, Capitais e as 9 Bases)")
    st.write(
        "Distribuição territorial das oportunidades com granularidade temática, cobrindo todas as 27 capitais, "
        "polos do interior e as **9 Bases Operacionais Estratégicas** (com anéis logísticos de até 250 km)."
    )

    # 1. Barra de Ações & Compartilhamento com Amigos
    st.markdown("#### 🚀 Compartilhamento & Exportação do Mapa")
    col_share1, col_share2 = st.columns([1, 1])

    caminho_mapa_html = "pncp_intelligence/data/processed/mapa_interativo_oportunidades_pncp.html"

    with col_share1:
        if os.path.exists(caminho_mapa_html):
            with open(caminho_mapa_html, "r", encoding="utf-8") as f_map:
                html_map_data = f_map.read()
            st.download_button(
                label="📥 Baixar Arquivo HTML do Mapa (Zero Dependência)",
                data=html_map_data,
                file_name="mapa_interativo_oportunidades_pncp.html",
                mime="text/html",
                help="Gera arquivo HTML autocontido. Qualquer pessoa pode abrir diretamente no Chrome/Safari em qualquer computador ou smartphone sem instalar nada."
            )
        else:
            st.info("Arquivo de mapa HTML sendo compilado...")

    with col_share2:
        with st.expander("🔗 Como passar este mapa para um amigo (3 Formas Rápidas)"):
            st.markdown("""
            **1. Enviar o Arquivo HTML (Mais Rápido & Sem Dependências):**
            - Baixe pelo botão ao lado e envie por WhatsApp, Email, Slack ou Google Drive.
            - O amigo dá dois cliques e o mapa abre imediatamente no navegador, 100% interativo com zoom, popups e filtros.

            **2. Link Web Gratuito no GitHub Pages:**
            - O mapa está salvo em `docs/index.html` no repositório.
            - No GitHub do projeto (`guimaraesca/icaro`), vá em **Settings -> Pages**.
            - Selecione **Branch: main** e pasta **/docs** -> Salvar.
            - O link fica disponível gratuitamente: `https://guimaraesca.github.io/icaro/`.

            **3. Link Público no Streamlit Community Cloud:**
            - Conecte o repositório em [share.streamlit.io](https://share.streamlit.io) apontando para `pncp_intelligence/dashboard/app.py`.
            - O dashboard inteiro fica online gratuitamente com link compartilhável!
            """)

    st.markdown("---")

    # 2. Renderização do Mapa Interativo
    st.markdown("#### 📍 Navegador Cartográfico Interativo")

    col_opt1, col_opt2, col_opt3 = st.columns([2, 2, 2])
    with col_opt1:
        exibir_raios = st.checkbox("Exibir Raio de 250 km das 9 Bases", value=True)
    with col_opt2:
        exibir_legenda = st.checkbox("Exibir Guia de Cores dos Temas", value=True)
    with col_opt3:
        filtro_geo_foco = st.selectbox(
            "Filtrar Localidades no Mapa:",
            ["Todas as Localidades", "Apenas Capitais & Bases", "Apenas Cidades das 9 Bases (<= 250 km)"]
        )

    if exibir_legenda:
        st.markdown("""
        <div style="background-color: #1E222D; padding: 12px 18px; border-radius: 8px; margin-bottom: 12px; font-size: 13px;">
            <b>Legenda Temática dos Marcadores:</b> &nbsp;&nbsp;
            <span style="color: #10B981;">🟢 Educação / IDEB / Robótica / Maker</span> &nbsp;|&nbsp;
            <span style="color: #F59E0B;">🟠 Políticas Públicas / Avaliações / M&A</span> &nbsp;|&nbsp;
            <span style="color: #8B5CF6;">🟣 IA / Ciência de Dados / Dashboards</span> &nbsp;|&nbsp;
            <span style="color: #3B82F6;">🔵 Plataformas & SaaS</span> &nbsp;|&nbsp;
            <span style="color: #EAB308;">⭐ As 9 Bases Operacionais (250 km)</span>
        </div>
        """, unsafe_allow_html=True)

    # Filtragem geográfica prévia se solicitada
    df_para_mapa = filtered_df.copy()
    if filtro_geo_foco == "Apenas Capitais & Bases":
        capitais_nomes = [c["nome"].lower() for c in CAPITAIS_INFO.values()]
        df_para_mapa = df_para_mapa[
            df_para_mapa["municipio_nome"].str.lower().isin(capitais_nomes) |
            (df_para_mapa["is_priority_geo"] == 1)
        ]
    elif filtro_geo_foco == "Apenas Cidades das 9 Bases (<= 250 km)":
        df_para_mapa = df_para_mapa[df_para_mapa["is_priority_geo"] == 1]

    if not df_para_mapa.empty:
        with st.spinner("Carregando mapa interativo com clusters e anéis logísticos..."):
            mapa_obj = GeoMapBuilder.criar_mapa_folium(
                df_para_mapa,
                mostrar_raios_bases=exibir_raios
            )
            html_folium = mapa_obj.get_root().render()
            components.html(html_folium, height=660, scrolling=True)
    else:
        st.warning("Nenhum edital com dados de localização para o filtro selecionado.")

    st.markdown("---")

    # 3. Análise Granular por Estados (UFs) e Capitais (Sem Pizza!)
    df_uf, df_muni = GeoMapBuilder.agregar_dados_geograficos(filtered_df)

    if not df_uf.empty:
        st.markdown("#### 📊 Distribuição Territorial & Granularidade Temática")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Estados (UFs) Mapeados", f"{len(df_uf)} / 27")
        m2.metric("Municípios Atendidos", formatar_inteiro(len(df_muni)))

        vol_capitais = 0.0
        capitais_nomes_set = {c["nome"].lower() for c in CAPITAIS_INFO.values()}
        if not df_muni.empty:
            vol_capitais = df_muni[df_muni["municipio"].str.lower().isin(capitais_nomes_set)]["valor_total_estimado"].sum()
        vol_total_geo = df_uf["valor_total_estimado"].sum()

        m3.metric(
            "Volume em Capitais",
            formatar_moeda_compacta(vol_capitais),
            help=f"Volume exato: {formatar_moeda_completa(vol_capitais)}"
        )
        m4.metric(
            "Volume no Interior",
            formatar_moeda_compacta(vol_total_geo - vol_capitais),
            help=f"Volume exato: {formatar_moeda_completa(vol_total_geo - vol_capitais)}"
        )

        # Gráficos de Barras Horizontais (Top UFs e Top Capitais)
        col_bar_uf, col_bar_cap = st.columns(2)

        with col_bar_uf:
            st.markdown("##### 🏛️ Top 10 Estados (UFs) por Volume Financeiro (R$)")
            top_ufs = df_uf.head(10).sort_values(by="valor_total_estimado", ascending=True).copy()
            top_ufs["valor_formatado"] = top_ufs["valor_total_estimado"].apply(formatar_moeda_compacta)
            fig_bar_uf = px.bar(
                top_ufs,
                x="valor_total_estimado",
                y="uf_sigla",
                orientation="h",
                color="regiao",
                title="Volume Financeiro Estimado por UF (R$)",
                labels={"valor_total_estimado": "Valor Total (R$)", "uf_sigla": "Estado (UF)", "regiao": "Região"},
                text="valor_formatado",
                hover_data={"capital": True, "total_editais": True, "tema_lider": True}
            )
            fig_bar_uf.update_layout(yaxis={"categoryorder": "total ascending"})
            fig_bar_uf = apply_pbi_theme(fig_bar_uf, height=380, is_dark=is_dark)
            st.plotly_chart(fig_bar_uf, use_container_width=True)

        with col_bar_cap:
            st.markdown("##### 🏙️ Top Capitais e Polos por Volume Financeiro (R$)")
            if not df_muni.empty:
                top_munis = df_muni.head(10).sort_values(by="valor_total_estimado", ascending=True).copy()
                top_munis["valor_formatado"] = top_munis["valor_total_estimado"].apply(formatar_moeda_compacta)
                fig_bar_cap = px.bar(
                    top_munis,
                    x="valor_total_estimado",
                    y="localidade",
                    orientation="h",
                    color="tema_lider",
                    title="Volume por Cidade / Polo Regional (R$)",
                    labels={"valor_total_estimado": "Valor Total (R$)", "localidade": "Município", "tema_lider": "Tema Líder"},
                    text="valor_formatado",
                    hover_data={"total_editais": True, "base_logistica": True}
                )
                fig_bar_cap.update_layout(yaxis={"categoryorder": "total ascending"})
                fig_bar_cap = apply_pbi_theme(fig_bar_cap, height=380, is_dark=is_dark)
                st.plotly_chart(fig_bar_cap, use_container_width=True)

        # Tabela Granular de Estados e Temas
        st.markdown("##### 📋 Matriz Estadual Detalhada (UFs, Capitais e Temas Líderes)")
        df_uf_tabela = df_uf.copy()
        df_uf_tabela["Total Licitado"] = df_uf_tabela["valor_total_estimado"].apply(formatar_moeda_compacta)
        df_uf_tabela["Valor Completo"] = df_uf_tabela["valor_total_estimado"].apply(formatar_moeda_completa)
        df_uf_tabela["Ticket Médio"] = df_uf_tabela["ticket_medio"].apply(formatar_moeda_completa)
        df_uf_tabela["Nº Editais"] = df_uf_tabela["total_editais"].apply(formatar_inteiro)

        st.dataframe(
            df_uf_tabela[[
                "uf_sigla", "capital", "regiao", "Nº Editais", "Total Licitado", "Valor Completo", "Ticket Médio", "tema_lider"
            ]].rename(columns={
                "uf_sigla": "UF",
                "capital": "Capital",
                "regiao": "Região",
                "tema_lider": "Tema Mais Demandado"
            }),
            use_container_width=True,
            hide_index=True
        )

        # Drill-Down por Estado: Inspecionar editais de uma UF
        st.markdown("##### 🔍 Drill-Down por Estado: Inspecionar Editais de uma UF")
        uf_opcoes = ["Selecione um Estado..."] + df_uf["uf_sigla"].tolist()
        uf_selecionada = st.selectbox("Escolha a UF para abrir todos os seus editais:", options=uf_opcoes)

        if uf_selecionada != "Selecione um Estado...":
            editais_uf = filtered_df[filtered_df["uf_sigla"] == uf_selecionada]
            st.write(f"Encontrados **{formatar_inteiro(len(editais_uf))} editais** em **{uf_selecionada}**:")
            cols_show_uf = [
                "municipio_nome", "razao_social_orgao", "modalidade_nome", "matched_category",
                "objeto_compra", "valor_total_estimado", "data_encerramento_proposta", "link_sistema_origem"
            ]
            cols_show_uf = [c for c in cols_show_uf if c in editais_uf.columns]
            display_uf = editais_uf[cols_show_uf].copy()
            if "valor_total_estimado" in display_uf.columns:
                display_uf["valor_total_estimado"] = display_uf["valor_total_estimado"].apply(formatar_moeda_completa)

            st.dataframe(
                display_uf,
                column_config={
                    "municipio_nome": "Município",
                    "valor_total_estimado": "Valor Estimado (R$)",
                    "link_sistema_origem": st.column_config.LinkColumn("Edital Oficial", display_text="Acessar Sistema")
                },
                use_container_width=True,
                hide_index=True
            )

    st.markdown("---")

    # 4. As 9 Bases Operacionais Estratégicas (Malha até 250 km)
    st.markdown("#### 🎯 Gestão Territorial das 9 Bases Operacionais (Raio 250 km)")
    st.write(
        "Polos operacionais estratégicos: **São Paulo (SP), Campinas (SP), Brasília (DF), Goiânia (GO), "
        "Joinville (SC), Recife (PE), Natal (RN), Fortaleza (CE) e Porto Alegre (RS)**."
    )

    from core.geo_utils import GeoIntelligence
    geo_intel = GeoIntelligence()
    df_cidades_alvo = geo_intel.get_dataframe()

    col_g1, col_g2 = st.columns([3, 2])
    with col_g1:
        st.markdown("##### Volume Financeiro por Hub Logístico")
        df_base_analytics = analytics.logistics_breakdown(filtered_df)
        if not df_base_analytics.empty:
            fig_base = px.bar(
                df_base_analytics,
                x="base_logistica",
                y="valor_estimado_total",
                color="faixa_raio",
                title="Oportunidades Mapeadas por Hub Logístico (R$)",
                labels={"base_logistica": "Hub Central", "valor_estimado_total": "Valor Total (R$)"},
                barmode="stack",
                color_discrete_sequence=px.colors.qualitative.Safe
            )
            fig_base = apply_pbi_theme(fig_base, height=380, is_dark=is_dark)
            st.plotly_chart(fig_base, use_container_width=True)
        else:
            st.info("Nenhuma oportunidade vinculada às 9 bases no filtro atual.")

    with col_g2:
        st.markdown("##### Cidades Alvo Mapeadas por Base Central")
        st.dataframe(
            df_cidades_alvo["base"].value_counts().reset_index().rename(columns={"base": "Hub Central", "count": "Cidades Mapeadas"}),
            use_container_width=True,
            hide_index=True
        )

    st.markdown("##### Catálogo de Municípios Estratégicos (Malha de 250 km)")
    st.dataframe(
        df_cidades_alvo,
        column_config={
            "cidade": "Município",
            "uf": "UF",
            "base": "Base Operacional",
            "distancia_km": st.column_config.NumberColumn("Distância (km)", format="%d km"),
            "faixa_raio": "Faixa de Raio",
            "porte": "Porte",
            "prioridade": "Prioridade Logística",
            "regiao": "Região"
        },
        use_container_width=True,
        hide_index=True,
        height=450
    )

# ----------------- MÓDULO 8: EXPLORADOR GRANULAR DE EDITAIS -----------------
elif menu_navegacao == "🔍 3. Detalhes":
    st.subheader("🔍 3. Detalhes (Explorador & Gestão)")
    st.subheader("Explorador Granular de Editais e Itens Unitários")

    if not filtered_df.empty:
        st.write("Selecione um edital na lista para carregar seus itens e especificações técnicas:")

        cols_grid = [
            "numero_controle_pncp", "razao_social_orgao", "uf_sigla", "modalidade_nome",
            "valor_total_estimado", "matched_subtema", "objeto_compra"
        ]
        display_grid = filtered_df[cols_grid].copy()
        if "valor_total_estimado" in display_grid.columns:
            display_grid["valor_total_estimado"] = display_grid["valor_total_estimado"].apply(formatar_moeda_completa)

        st.dataframe(
            display_grid,
            column_config={
                "numero_controle_pncp": "Controle PNCP",
                "razao_social_orgao": "Órgão",
                "uf_sigla": "UF",
                "modalidade_nome": "Modalidade",
                "valor_total_estimado": "Valor Estimado (R$)",
                "matched_subtema": "Subtema",
                "objeto_compra": "Objeto"
            },
            use_container_width=True,
            hide_index=True,
            height=680
        )

        selected_pncp = st.selectbox(
            "Inspecionar itens do edital (Número de Controle PNCP):",
            options=filtered_df["numero_controle_pncp"].tolist()
        )

        if selected_pncp:
            with db.get_connection() as conn:
                itens_edital = pd.read_sql_query(
                    "SELECT numero_item, descricao, quantidade, unidade_medida, valor_unitario_estimado, valor_total_estimado, situacao_item_nome FROM itens_contratacao WHERE numero_controle_pncp = ? ORDER BY numero_item",
                    conn,
                    params=(selected_pncp,)
                )

            if not itens_edital.empty:
                st.markdown(f"##### Itens do Edital `{selected_pncp}`")
                display_itens = itens_edital.copy()
                if "quantidade" in display_itens.columns:
                    display_itens["quantidade"] = display_itens["quantidade"].apply(formatar_inteiro)
                if "valor_unitario_estimado" in display_itens.columns:
                    display_itens["valor_unitario_estimado"] = display_itens["valor_unitario_estimado"].apply(formatar_moeda_completa)
                if "valor_total_estimado" in display_itens.columns:
                    display_itens["valor_total_estimado"] = display_itens["valor_total_estimado"].apply(formatar_moeda_completa)
                st.dataframe(
                    display_itens,
                    column_config={
                        "numero_item": "Item",
                        "descricao": "Descrição Técnica",
                        "quantidade": "Qtd",
                        "unidade_medida": "Unidade",
                        "valor_unitario_estimado": "Unitário (R$)",
                        "valor_total_estimado": "Total (R$)",
                        "situacao_item_nome": "Situação"
                    },
                    use_container_width=True,
                    hide_index=True,
                    height=420
                )
            else:
                st.info("Nenhum item unitário indexado ainda para este edital específico.")

            # Linhagem detalhada do edital selecionado (Pilar 5: Lineage)
            lin_info = lineage_for_edital(str(db.db_path), selected_pncp)
            if lin_info:
                with st.expander(f"🧬 Linhagem de Dados & Proveniência do Edital `{selected_pncp}`", expanded=False):
                    c_lin1, c_lin2, c_lin3 = st.columns(3)
                    with c_lin1:
                        st.markdown(f"**Endpoint de Origem:** `{lin_info.get('source_endpoint') or 'PNCP API'}`")
                        st.markdown(f"**Primeira Captura (Run):** `{lin_info.get('first_run_id') or 'N/A'}`")
                    with c_lin2:
                        st.markdown(f"**Última Atualização (Run):** `{lin_info.get('last_run_id') or 'N/A'}`")
                        st.markdown(f"**Versão Dicionário (Hash):** `{lin_info.get('keywords_hash') or 'N/A'}`")
                    with c_lin3:
                        st.markdown(f"**Data Classificação:** `{lin_info.get('classified_at') or lin_info.get('created_at') or 'N/A'}`")
                        st.markdown(f"**Palavras-chave Encontradas:** `{', '.join(lin_info.get('matched_keywords') or []) or 'N/A'}`")

# ----------------- MÓDULO 9: GESTÃO DE COLETAS & EXPANSÃO -----------------
    st.markdown("---")
    st.subheader("⚙️ Gestão de Coletas & Expansão")
    st.subheader("Exportação e Gerenciamento do Pipeline")

    c_exp1, c_exp2 = st.columns(2)

    with c_exp1:
        st.markdown("#### 📥 Exportar Base Completa")
        st.write("Gere planilhas multi-abas formatadas em Excel (.xlsx) e arquivos Parquet de alta performance.")
        if st.button("🚀 Gerar e Atualizar Arquivos Exportados", type="primary"):
            with st.spinner("Compilando dados e gerando Excel..."):
                paths = exporter.export_all()
                st.success(f"Arquivos gerados com sucesso em `{paths['excel']}`!")

        # Download do Excel diretamente pelo Streamlit
        excel_file_path = "pncp_intelligence/data/processed/pncp_mercado_analise_completa.xlsx"
        try:
            with open(excel_file_path, "rb") as f:
                st.download_button(
                    label="⬇️ Baixar Relatório em Excel (.xlsx)",
                    data=f,
                    file_name="pncp_analise_oportunidades.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        except Exception:
            pass

    with c_exp2:
        st.markdown("#### 🔄 Executar Nova Coleta no PNCP")
        st.write("Dispare a busca de novas oportunidades e histórico diretamente na API do PNCP:")
        modo_coleta = st.selectbox(
            "Modo de Coleta:",
            [
                "Oportunidades Ativas (Propostas Abertas Hoje)",
                "Últimos 30 Dias",
                "Últimos 90 Dias",
                "Últimos 2 Anos (~730 dias - Padrão)",
                "Últimos 3 Anos (Expansão 2023 - ~1.095 dias)",
                "Últimos 4 Anos (Integral Lei 14.133 - Desde 2021)"
            ]
        )

        if st.button("Iniciar Coleta Agora"):
            with st.spinner("Consultando API de Busca e Propostas Abertas do PNCP..."):
                d_fim = datetime.today().date()
                if modo_coleta == "Oportunidades Ativas (Propostas Abertas Hoje)":
                    op_search = collector.collect_by_search_terms(status="recebendo_proposta", max_pages_per_query=2)
                    st.cache_data.clear()
                    st.success(f"Coleta concluída! {formatar_inteiro(len(op_search))} oportunidades ativas indexadas diretamente nos termos prioritários.")
                else:
                    if modo_coleta == "Últimos 30 Dias":
                        d_ini = d_fim - pd.Timedelta(days=30)
                    elif modo_coleta == "Últimos 90 Dias":
                        d_ini = d_fim - pd.Timedelta(days=90)
                    elif "2 Anos" in modo_coleta:
                        d_ini = d_fim - pd.Timedelta(days=730)
                    elif "3 Anos" in modo_coleta:
                        d_ini = d_fim - pd.Timedelta(days=1095)
                    else:
                        d_ini = d_fim - pd.Timedelta(days=1460)
                    res = collector.collect_period(d_ini, d_fim)
                    st.cache_data.clear()
                    st.success(f"Coleta concluída! {formatar_inteiro(res['total_scanned'])} analisados, {formatar_inteiro(res['total_matches'])} editais relevantes salvos e {formatar_inteiro(res['total_items_saved'])} itens indexados.")
                st.rerun()

    st.markdown("---")

    # Guia Estratégico de Expansão da Base
    st.markdown("#### 💡 Como Aumentar a Base de Editais (3 Formas Mais Efetivas)")
    c_strat1, c_strat2, c_strat3 = st.columns(3)
    with c_strat1:
        st.markdown("""
        <div style="background: rgba(59, 130, 246, 0.08); border: 1px solid rgba(59, 130, 246, 0.2); border-radius: 10px; padding: 14px; min-height: 190px;">
            <h5 style="margin: 0 0 6px 0; color: #60A5FA;">1. Expansão de Vocabulário (Maior Impacto)</h5>
            <p style="font-size: 12px; color: #CBD5E1; margin: 0;">
                O PNCP possui centenas de milhares de editais. O coletor filtra pelo dicionário <code>keywords.yaml</code>. 
                Adicionar sinônimos e novos termos (ex: gestão pública, saúde digital, ERP municipal, cidades inteligentes) 
                faz o coletor indexar milhares de editais que hoje são descartados.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with c_strat2:
        st.markdown("""
        <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 10px; padding: 14px; min-height: 190px;">
            <h5 style="margin: 0 0 6px 0; color: #34D399;">2. Janela Histórica Estendida (3 a 4 Anos)</h5>
            <p style="font-size: 12px; color: #CBD5E1; margin: 0;">
                A Lei 14.133/2021 foi sancionada em abril de 2021. Selecionando <b>Últimos 4 Anos</b> no coletor acima, 
                você resgata todo o histórico integral desde a origem da nova lei de licitações, aumentando o banco em 50% a 100%.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with c_strat3:
        st.markdown("""
        <div style="background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.2); border-radius: 10px; padding: 14px; min-height: 190px;">
            <h5 style="margin: 0 0 6px 0; color: #FBBF24;">3. Ingestão Automatizada Diária</h5>
            <p style="font-size: 12px; color: #CBD5E1; margin: 0;">
                O governo publica entre 300 e 800 novos editais todos os dias úteis. Com automação em segundo plano 
                (via <code>/schedule</code> ou cron), o banco cresce diariamente de forma passiva sem intervenção manual.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 📈 Estatísticas Internas do Banco")
    stats = db.get_stats()
    st.json(stats)

    # ----------------- PAINEL DE OBSERVABILIDADE DE DADOS (5 PILARES) -----------------
    st.markdown("---")
    st.markdown("### 🩺 Observabilidade de Dados & Qualidade em Produção (5 Pilares)")
    st.caption("Auditoria contínua da saúde da base de dados cobrindo Freshness, Distribution, Volume, Schema e Lineage.")

    try:
        report = evaluate_health(str(db.db_path))
        counts = report.counts()
        pillars_status = report.by_pillar()

        c_obs1, c_obs2, c_obs3, c_obs4, c_obs5 = st.columns(5)
        with c_obs1:
            icon = "✅" if pillars_status.get("Freshness") == "PASS" else ("⚠️" if pillars_status.get("Freshness") == "WARN" else "❌")
            st.metric("1. Freshness", f"{icon} {pillars_status.get('Freshness')}")
        with c_obs2:
            icon = "✅" if pillars_status.get("Distribution") == "PASS" else ("⚠️" if pillars_status.get("Distribution") == "WARN" else "❌")
            st.metric("2. Distribution", f"{icon} {pillars_status.get('Distribution')}")
        with c_obs3:
            icon = "✅" if pillars_status.get("Volume") == "PASS" else ("⚠️" if pillars_status.get("Volume") == "WARN" else "❌")
            st.metric("3. Volume", f"{icon} {pillars_status.get('Volume')}")
        with c_obs4:
            icon = "✅" if pillars_status.get("Schema") == "PASS" else ("⚠️" if pillars_status.get("Schema") == "WARN" else "❌")
            st.metric("4. Schema", f"{icon} {pillars_status.get('Schema')}")
        with c_obs5:
            icon = "✅" if pillars_status.get("Lineage") == "PASS" else ("⚠️" if pillars_status.get("Lineage") == "WARN" else "❌")
            st.metric("5. Lineage", f"{icon} {pillars_status.get('Lineage')}")

        st.markdown("##### 📋 Matriz de Verificações de Qualidade")
        df_checks = pd.DataFrame(report.to_dicts())
        if not df_checks.empty:
            st.dataframe(
                df_checks,
                column_config={
                    "pillar": "Pilar",
                    "name": "Verificação",
                    "status": "Status",
                    "observed": "Observado",
                    "expected": "Esperado",
                    "detail": "Detalhes Técnicos"
                },
                use_container_width=True,
                hide_index=True
            )

        with st.expander("🗺️ Arquitetura de Linhagem de Dados (Pipeline Lineage)", expanded=False):
            st.markdown("##### Etapas de Transformação da Informação")
            st.dataframe(pd.DataFrame(LINEAGE_STAGES), use_container_width=True, hide_index=True)
            st.markdown("##### Linhagem dos Indicadores & Métricas Chave")
            st.dataframe(pd.DataFrame(INDICATOR_LINEAGE), use_container_width=True, hide_index=True)

    except Exception as e:
        st.warning(f"Não foi possível avaliar o relatório de observabilidade no momento: {e}")

# ----------------- MÓDULO 4: OBSERVABILIDADE DE DADOS (5 PILARES) -----------------
elif menu_navegacao == "🛡️ 4. Observabilidade":
    st.subheader("🛡️ 4. Central de Observabilidade de Dados & Governança (5 Pilares)")
    st.caption(
        "Monitoramento contínuo da saúde do pipeline em produção cobrindo os 5 pilares canônicos: "
        "**Freshness, Volume, Distribution, Schema e Lineage** (conforme SLA e contratos da Lei 14.133/2021)."
    )

    try:
        report = evaluate_health(str(db.db_path))
        counts = report.counts()
        pillars_status = report.by_pillar()

        c_obs1, c_obs2, c_obs3, c_obs4, c_obs5 = st.columns(5)
        with c_obs1:
            icon = "🟢" if pillars_status.get("Freshness") == "PASS" else ("🟡" if pillars_status.get("Freshness") == "WARN" else "🔴")
            st.metric("1. Freshness", f"{icon} {pillars_status.get('Freshness')}", "Sincronização Diária")
        with c_obs2:
            icon = "🟢" if pillars_status.get("Volume") == "PASS" else ("🟡" if pillars_status.get("Volume") == "WARN" else "🔴")
            st.metric("2. Volume", f"{icon} {pillars_status.get('Volume')}", f"{formatar_inteiro(len(df_raw))} editais")
        with c_obs3:
            icon = "🟢" if pillars_status.get("Distribution") == "PASS" else ("🟡" if pillars_status.get("Distribution") == "WARN" else "🔴")
            st.metric("3. Distribution", f"{icon} {pillars_status.get('Distribution')}", "Valores e Domínios")
        with c_obs4:
            icon = "🟢" if pillars_status.get("Schema") == "PASS" else ("🟡" if pillars_status.get("Schema") == "WARN" else "🔴")
            st.metric("4. Schema", f"{icon} {pillars_status.get('Schema')}", "Contrato de API")
        with c_obs5:
            icon = "🟢" if pillars_status.get("Lineage") == "PASS" else ("🟡" if pillars_status.get("Lineage") == "WARN" else "🔴")
            st.metric("5. Lineage", f"{icon} {pillars_status.get('Lineage')}", "Rastreio Fim a Fim")

        st.markdown("---")

        tab_checks, tab_lineage, tab_stats = st.tabs([
            "📋 Matriz de Verificações",
            "🗺️ Arquitetura de Linhagem",
            "📈 Estatísticas do Banco"
        ])

        with tab_checks:
            st.markdown("##### 📋 Matriz Executiva de Verificações de Qualidade")
            st.caption("Verificações automáticas aplicadas sobre o banco de dados:")
            df_checks = pd.DataFrame(report.to_dicts())
            if not df_checks.empty:
                st.dataframe(
                    df_checks,
                    column_config={
                        "pillar": "Pilar",
                        "name": "Verificação",
                        "status": "Status",
                        "observed": "Observado",
                        "expected": "Esperado",
                        "detail": "Detalhes Técnicos"
                    },
                    use_container_width=True,
                    hide_index=True
                )

        with tab_lineage:
            st.markdown("##### 🗺️ Etapas de Transformação da Informação (Data Lineage)")
            st.caption("Da coleta na API pública do PNCP até as decisões do Command Center:")
            st.dataframe(pd.DataFrame(LINEAGE_STAGES), use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("##### 🎯 Linhagem dos Indicadores & Métricas Chave")
            st.dataframe(pd.DataFrame(INDICATOR_LINEAGE), use_container_width=True, hide_index=True)

        with tab_stats:
            st.markdown("##### 📈 Metadados do Banco SQLite Local")
            stats = db.get_stats()
            st.json(stats)

    except Exception as e:
        st.warning(f"Não foi possível avaliar o relatório de observabilidade no momento: {e}")

# ----------------- MÓDULO 5: CENTRAL I.C.A.R.O. (AGÊNCIAS & PRIVADO) -----------------
elif menu_navegacao == "🦅 5. I.C.A.R.O. (Agências & Privado)":
    render_icaro_module(is_dark=is_dark)
