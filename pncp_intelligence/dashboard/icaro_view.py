"""Módulo de Visualização da Central I.C.A.R.O. no Dashboard Streamlit.

Apresenta oportunidades de consultoria internacional (UNESCO, PNUD, OEI, UNICEF),
chamadas públicas do terceiro setor (Fundações) e posições de GovTechs/EdTechs
analisadas semanticamente pela IA (Google Gemini) para o perfil de Carlos Artur e Felipe Souza.
"""

import glob
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st


def load_icaro_opportunities() -> List[Dict[str, Any]]:
    """Carrega a base estruturada de oportunidades do I.C.A.R.O."""
    potential_paths = [
        Path(__file__).resolve().parents[1] / "data" / "icaro" / "oportunidades_icaro.json",
        Path.cwd() / "pncp_intelligence" / "data" / "icaro" / "oportunidades_icaro.json",
        Path(__file__).resolve().parents[3] / "SixSigma" / "data" / "db" / "oportunidades_icaro.json",
        Path("/Users/carlosarturguimaraes/Documents/SixSigma/data/db/oportunidades_icaro.json"),
    ]

    for p in potential_paths:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and data:
                        return data
            except Exception:
                pass

    return []


def load_icaro_historical_reports() -> List[Dict[str, str]]:
    """Carrega briefings e relatórios em markdown do I.C.A.R.O."""
    potential_dirs = [
        Path(__file__).resolve().parents[3] / "SixSigma" / "data" / "relatorios",
        Path("/Users/carlosarturguimaraes/Documents/SixSigma/data/relatorios"),
    ]

    reports = []
    for d in potential_dirs:
        if d.exists() and d.is_dir():
            files = sorted(glob.glob(str(d / "relatorio_*.md")), reverse=True)
            for fpath in files[:20]:
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        fname = os.path.basename(fpath)
                        reports.append({
                            "filename": fname,
                            "path": fpath,
                            "content": f.read()
                        })
                except Exception:
                    pass
            if reports:
                break

    return reports


def render_icaro_module(is_dark: bool = False):
    """Renderiza a aba executiva I.C.A.R.O. no painel do Streamlit."""
    theme_bg = "#0F172A" if is_dark else "#F8FAFC"
    card_bg = "#1E293B" if is_dark else "#FFFFFF"
    border_color = "#334155" if is_dark else "#E2E8F0"
    text_primary = "#F8FAFC" if is_dark else "#0F172A"
    text_muted = "#94A3B8" if is_dark else "#64748B"

    st.subheader("🦅 5. Central I.C.A.R.O. • Oportunidades Internacionais & Privadas")
    st.caption(
        "Monitoramento autônomo de consultorias internacionais (**UNESCO, PNUD, OEI, UNICEF**), "
        "chamadas públicas de fundações (**Lemann, Itaú Social, Unibanco**) e posições em **GovTechs & EdTechs**, "
        "com triagem e aderência semântica realizada via **Google Gemini**."
    )

    opps = load_icaro_opportunities()

    if not opps:
        st.info(
            "ℹ️ Nenhuma oportunidade encontrada na base local do I.C.A.R.O. "
            "Certifique-se de que o arquivo `oportunidades_icaro.json` esteja sincronizado."
        )
        return

    # 1. Métricas de Topo
    total_opps = len(opps)
    altas = [o for o in opps if o.get("score") == "Alta"]
    medias = [o for o in opps if o.get("score") == "Média"]
    grupos_unicos = sorted(list({o.get("grupo", "geral").lower() for o in opps}))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Oportunidades Mapeadas", f"{total_opps}", "Acervo Estratégico")
    with c2:
        st.metric("🟢 Alta Aderência (IA)", f"{len(altas)}", "Convergência Máxima")
    with c3:
        st.metric("🟡 Média Aderência (IA)", f"{len(medias)}", "Oportunidades Adjacentes")
    with c4:
        st.metric("Setores Cobertos", f"{len(grupos_unicos)} Setores", "Agências, ONGs e Privado")

    st.markdown("---")

    # 2. Filtros Laterais / Superiores
    f_col1, f_col2, f_col3 = st.columns([1.2, 1.2, 2.0])

    with f_col1:
        opcoes_grupo = ["Todos os Setores"] + [g.upper() for g in grupos_unicos]
        grupo_sel = st.selectbox("Filtrar por Setor:", opcoes_grupo, index=0)

    with f_col2:
        opcoes_score = ["Todas as Aderências", "🟢 Apenas Alta Aderência", "🟡 Apenas Média Aderência"]
        score_sel = st.selectbox("Filtrar por Score:", opcoes_score, index=0)

    with f_col3:
        busca_termo = st.text_input("🔍 Busca rápida (cargo, contratante, termo de referência):", placeholder="Ex: UNESCO, dados, BNCC, avaliação, remoto...")

    # Aplica filtros
    filtered_opps = opps.copy()
    if grupo_sel != "Todos os Setores":
        filtered_opps = [o for o in filtered_opps if o.get("grupo", "").lower() == grupo_sel.lower()]

    if "Alta Aderência" in score_sel:
        filtered_opps = [o for o in filtered_opps if o.get("score") == "Alta"]
    elif "Média Aderência" in score_sel:
        filtered_opps = [o for o in filtered_opps if o.get("score") == "Média"]

    if busca_termo:
        termo_clean = busca_termo.lower().strip()
        filtered_opps = [
            o for o in filtered_opps
            if termo_clean in o.get("cargo", "").lower()
            or termo_clean in o.get("objeto", "").lower()
            or termo_clean in o.get("fonte_orgao", "").lower()
            or termo_clean in o.get("reasoning", "").lower()
            or termo_clean in o.get("local", "").lower()
        ]

    tab_cards, tab_tabela, tab_relatorios = st.tabs([
        f"🎯 Oportunidades em Destaque ({len(filtered_opps)})",
        "📊 Tabela de Decisão & Exportação",
        "📰 Relatórios Diários do I.C.A.R.O."
    ])

    # ---------------- TAB 1: CARDS DE OPORTUNIDADES ----------------
    with tab_cards:
        if not filtered_opps:
            st.info("Nenhuma oportunidade encontrada com os filtros selecionados.")
        else:
            for idx, item in enumerate(filtered_opps, 1):
                score = item.get("score", "Alta")
                badge_color = "#10B981" if score == "Alta" else "#F59E0B"
                badge_bg = "rgba(16, 185, 129, 0.15)" if score == "Alta" else "rgba(245, 158, 11, 0.15)"

                cargo = item.get("cargo") or item.get("titulo")
                fonte = item.get("fonte_orgao") or item.get("grupo", "Geral").upper()
                local = item.get("local") or "Remoto / Híbrido"
                contrato = item.get("contrato") or "Consultoria por Produto"
                valor = item.get("valor") or "Não informado"
                prazo = item.get("prazo") or "Ver Edital"
                objeto = item.get("objeto") or ""
                reasoning = item.get("reasoning") or ""
                url = item.get("url") or ""
                data_col = item.get("data_coleta") or ""

                with st.expander(f"#{idx} • {fonte} • {cargo[:80]}", expanded=(idx <= 3)):
                    c_det1, c_det2 = st.columns([3, 1])
                    with c_det1:
                        st.markdown(f"### {cargo}")
                        st.markdown(
                            f"<span style='background-color: {badge_bg}; color: {badge_color}; padding: 3px 10px; border-radius: 6px; font-weight: bold; font-size: 13px;'>"
                            f"Grau de Aderência: {score}</span>"
                            f" &nbsp;•&nbsp; 🏛️ <b>Organização:</b> {fonte} &nbsp;•&nbsp; 📅 Data Mapeada: {data_col}",
                            unsafe_allow_html=True
                        )
                    with c_det2:
                        if url:
                            st.link_button("🔗 Acessar Vaga / Edital", url, use_container_width=True)

                    st.markdown("---")

                    col_info1, col_info2, col_info3 = st.columns(3)
                    with col_info1:
                        st.markdown(f"📍 **Local:** {local}")
                        st.markdown(f"📄 **Contrato:** {contrato}")
                    with col_info2:
                        st.markdown(f"💰 **Remuneração:** {valor}")
                        st.markdown(f"⏳ **Prazo de Inscrição:** {prazo}")
                    with col_info3:
                        st.markdown(f"🏷️ **Setor:** `{item.get('grupo', 'geral').upper()}`")

                    if objeto and objeto != "Não informado":
                        st.markdown(f"📝 **Escopo / Objeto da Chamada:**\n> {objeto}")

                    if reasoning:
                        st.markdown(
                            f"<div style='background-color: {theme_bg}; border-left: 4px solid {badge_color}; padding: 10px 14px; border-radius: 6px; margin-top: 10px;'>"
                            f"🤖 <b>Parecer Semântico da IA (Google Gemini):</b><br>"
                            f"<span style='color: {text_primary}; font-size: 13px;'>{reasoning}</span>"
                            f"</div>",
                            unsafe_allow_html=True
                        )

    # ---------------- TAB 2: TABELA DE DECISÃO ----------------
    with tab_tabela:
        df_export = pd.DataFrame(filtered_opps)
        if not df_export.empty:
            cols_show = ["data_coleta", "score", "fonte_orgao", "cargo", "local", "valor", "prazo", "url"]
            df_display = df_export[[c for c in cols_show if c in df_export.columns]].copy()
            df_display.rename(columns={
                "data_coleta": "Data",
                "score": "Aderência",
                "fonte_orgao": "Organização",
                "cargo": "Cargo / Oportunidade",
                "local": "Localização",
                "valor": "Remuneração",
                "prazo": "Prazo",
                "url": "Link Oficial"
            }, inplace=True)

            st.dataframe(
                df_display,
                column_config={
                    "Link Oficial": st.column_config.LinkColumn("Link da Chamada", display_text="🔗 Acessar"),
                },
                use_container_width=True,
                hide_index=True
            )

            csv_data = df_export.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Baixar Oportunidades em CSV",
                csv_data,
                "oportunidades_icaro_consolidadas.csv",
                "text/csv",
                key="dl_icaro_csv"
            )

    # ---------------- TAB 3: RELATÓRIOS HISTÓRICOS ----------------
    with tab_relatorios:
        st.markdown("##### 📰 Relatórios e Briefings Executivos Anteriores")
        st.caption("Histórico das varreduras diárias geradas pelo motor I.C.A.R.O.:")

        relatorios = load_icaro_historical_reports()
        if not relatorios:
            st.info("Nenhum relatório histórico (.md) disponível nesta instalação.")
        else:
            sel_rel = st.selectbox(
                "Selecione um relatório para leitura:",
                [r["filename"] for r in relatorios],
                index=0
            )
            rel_escolhido = next((r for r in relatorios if r["filename"] == sel_rel), None)
            if rel_escolhido:
                st.markdown(
                    f"<div style='background-color: {card_bg}; border: 1px solid {border_color}; padding: 18px; border-radius: 8px; margin-top: 10px; max-height: 500px; overflow-y: auto;'>"
                    f"{rel_escolhido['content']}"
                    f"</div>",
                    unsafe_allow_html=True
                )
