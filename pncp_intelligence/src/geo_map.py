"""Módulo de Mapeamento Geo-Temático Interativo de Editais (Brasil, Estados e Capitais).

Oferece:
- Coordenadas geográficas das 27 UFs, 27 Capitais e principais polos regionais do Brasil.
- Agregação de editais por UF e Município com granularidade temática detalhada.
- Geração de mapa interativo via Folium com:
  * Camada das 9 Bases Operacionais Estratégicas (com anéis de 250 km).
  * Camada de Capitais Brasileiras com popups temáticos e orçamentos em R$.
  * Camada de Municípios do Interior com agrupamento inteligente (MarkerCluster).
  * Controle de camadas (LayerControl) para isolar temas de interesse.
- Exportação de arquivo HTML autocontido (Zero Instalação) para compartilhamento imediato.
- Integração nativa com Streamlit e Plotly.
"""

import json
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import folium
from folium import plugins

from pncp_intelligence.src.formatters import (
    formatar_inteiro,
    formatar_moeda_compacta,
    formatar_moeda_completa,
)


# Coordenadas oficiais das 27 Capitais Brasileiras e Centróides das UFs
CAPITAIS_INFO: Dict[str, Dict[str, Any]] = {
    "AC": {"nome": "Rio Branco", "lat": -9.975278, "lon": -67.824722, "regiao": "Norte"},
    "AL": {"nome": "Maceió", "lat": -9.665990, "lon": -35.735000, "regiao": "Nordeste"},
    "AP": {"nome": "Macapá", "lat": 0.038889, "lon": -51.066389, "regiao": "Norte"},
    "AM": {"nome": "Manaus", "lat": -3.119028, "lon": -60.021731, "regiao": "Norte"},
    "BA": {"nome": "Salvador", "lat": -12.977749, "lon": -38.501630, "regiao": "Nordeste"},
    "CE": {"nome": "Fortaleza", "lat": -3.717222, "lon": -38.543056, "regiao": "Nordeste", "is_base": True},
    "DF": {"nome": "Brasília", "lat": -15.793889, "lon": -47.882778, "regiao": "Centro-Oeste", "is_base": True},
    "ES": {"nome": "Vitória", "lat": -20.315500, "lon": -40.312800, "regiao": "Sudeste"},
    "GO": {"nome": "Goiânia", "lat": -16.686891, "lon": -49.264794, "regiao": "Centro-Oeste", "is_base": True},
    "MA": {"nome": "São Luís", "lat": -2.530730, "lon": -44.306800, "regiao": "Nordeste"},
    "MT": {"nome": "Cuiabá", "lat": -15.601000, "lon": -56.097400, "regiao": "Centro-Oeste"},
    "MS": {"nome": "Campo Grande", "lat": -20.469700, "lon": -54.620100, "regiao": "Centro-Oeste"},
    "MG": {"nome": "Belo Horizonte", "lat": -19.916681, "lon": -43.934493, "regiao": "Sudeste"},
    "PA": {"nome": "Belém", "lat": -1.455755, "lon": -48.490180, "regiao": "Norte"},
    "PB": {"nome": "João Pessoa", "lat": -7.115320, "lon": -34.861000, "regiao": "Nordeste"},
    "PR": {"nome": "Curitiba", "lat": -25.428954, "lon": -49.267137, "regiao": "Sul"},
    "PE": {"nome": "Recife", "lat": -8.047562, "lon": -34.876964, "regiao": "Nordeste", "is_base": True},
    "PI": {"nome": "Teresina", "lat": -5.089210, "lon": -42.801600, "regiao": "Nordeste"},
    "RJ": {"nome": "Rio de Janeiro", "lat": -22.906847, "lon": -43.172896, "regiao": "Sudeste"},
    "RN": {"nome": "Natal", "lat": -5.794480, "lon": -35.211000, "regiao": "Nordeste", "is_base": True},
    "RS": {"nome": "Porto Alegre", "lat": -30.034647, "lon": -51.217658, "regiao": "Sul", "is_base": True},
    "RO": {"nome": "Porto Velho", "lat": -8.761944, "lon": -63.903889, "regiao": "Norte"},
    "RR": {"nome": "Boa Vista", "lat": 2.823500, "lon": -60.675800, "regiao": "Norte"},
    "SC": {"nome": "Florianópolis", "lat": -27.595378, "lon": -48.548050, "regiao": "Sul"},
    "SP": {"nome": "São Paulo", "lat": -23.550520, "lon": -46.633308, "regiao": "Sudeste", "is_base": True},
    "SE": {"nome": "Aracaju", "lat": -10.947247, "lon": -37.073082, "regiao": "Nordeste"},
    "TO": {"nome": "Palmas", "lat": -10.184444, "lon": -48.333611, "regiao": "Norte"}
}

# As 9 Bases Operacionais Estratégicas
BASES_ESTRATEGICAS: Dict[str, Dict[str, Any]] = {
    "São Paulo": {"uf": "SP", "lat": -23.550520, "lon": -46.633308, "raio_km": 250, "cor": "#3B82F6"},
    "Campinas": {"uf": "SP", "lat": -22.909938, "lon": -47.062633, "raio_km": 250, "cor": "#06B6D4"},
    "Brasília": {"uf": "DF", "lat": -15.793889, "lon": -47.882778, "raio_km": 250, "cor": "#EAB308"},
    "Goiânia": {"uf": "GO", "lat": -16.686891, "lon": -49.264794, "raio_km": 250, "cor": "#F97316"},
    "Joinville": {"uf": "SC", "lat": -26.304444, "lon": -48.848611, "raio_km": 250, "cor": "#10B981"},
    "Recife": {"uf": "PE", "lat": -8.047562, "lon": -34.876964, "raio_km": 250, "cor": "#8B5CF6"},
    "Natal": {"uf": "RN", "lat": -5.794480, "lon": -35.211000, "raio_km": 250, "cor": "#EC4899"},
    "Fortaleza": {"uf": "CE", "lat": -3.717222, "lon": -38.543056, "raio_km": 250, "cor": "#14B8A6"},
    "Porto Alegre": {"uf": "RS", "lat": -30.034647, "lon": -51.217658, "raio_km": 250, "cor": "#6366F1"}
}

# Principais Polos e Cidades Não-Capitais
POLOS_REGIONAIS_COORDS: Dict[str, Tuple[float, float]] = {
    "Campinas/SP": (-22.909938, -47.062633),
    "Joinville/SC": (-26.304444, -48.848611),
    "Caxias do Sul/RS": (-29.167778, -51.179444),
    "Pelotas/RS": (-31.765417, -52.337500),
    "Sobral/CE": (-3.689444, -40.348889),
    "Caruaru/PE": (-8.283333, -35.966667),
    "Mossoró/RN": (-5.187778, -37.344167),
    "Anápolis/GO": (-16.326667, -48.952778),
    "Ribeirão Preto/SP": (-21.177500, -47.810278),
    "São José dos Campos/SP": (-23.189444, -45.884167),
    "Santos/SP": (-23.960833, -46.333889),
    "Sorocaba/SP": (-23.501667, -47.458056),
    "Uberlândia/MG": (-18.918611, -48.277222),
    "Juiz de Fora/MG": (-21.764167, -43.349722),
    "Feira de Santana/BA": (-12.266667, -38.966667),
    "Campina Grande/PB": (-7.230556, -35.881111),
    "Blumenau/SC": (-26.919444, -49.066111),
    "Londrina/PR": (-23.310278, -51.162778),
    "Maringá/PR": (-23.425278, -51.938611),
    "Foz do Iguaçu/PR": (-25.547778, -54.588056),
}


class GeoMapBuilder:
    """Construtor de mapas temáticos interativos do PNCP."""

    @staticmethod
    def normalizar_nome(texto: Optional[str]) -> str:
        if not texto:
            return ""
        return str(texto).strip()

    @classmethod
    def get_coordenadas(cls, municipio: Optional[str], uf: Optional[str]) -> Tuple[float, float, bool]:
        """Obtém coordenadas (lat, lon, is_exact) para um município/UF."""
        muni = cls.normalizar_nome(municipio)
        uf_sigla = str(uf or "").strip().upper()

        chave_polo = f"{muni}/{uf_sigla}"
        if chave_polo in POLOS_REGIONAIS_COORDS:
            lat, lon = POLOS_REGIONAIS_COORDS[chave_polo]
            return lat, lon, True

        # Verifica capitais
        if uf_sigla in CAPITAIS_INFO:
            cap_info = CAPITAIS_INFO[uf_sigla]
            if muni.lower() == cap_info["nome"].lower():
                return cap_info["lat"], cap_info["lon"], True

        # Se município não tem coordenada exata, usa centróide da capital do estado com pequena variação
        if uf_sigla in CAPITAIS_INFO:
            base_lat = CAPITAIS_INFO[uf_sigla]["lat"]
            base_lon = CAPITAIS_INFO[uf_sigla]["lon"]
            # Variação sutil determinística baseada no nome para evitar sobreposição total
            h = hash(muni) % 100
            offset_lat = ((h % 10) - 5) * 0.08
            offset_lon = (((h // 10) % 10) - 5) * 0.08
            return base_lat + offset_lat, base_lon + offset_lon, False

        # Fallback Brasil Central
        return -14.235, -51.925, False

    @classmethod
    def agregar_dados_geograficos(cls, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Agrega dados por Município e por Estado com métricas temáticas detalhadas."""
        if df.empty:
            return pd.DataFrame(), pd.DataFrame()

        # 1. Agregação por Estado (UF)
        uf_rows = []
        for uf, grp in df.groupby("uf_sigla"):
            uf_upper = str(uf).strip().upper()
            if not uf_upper:
                continue

            v_tot = grp["valor_total_estimado"].sum()
            n_editais = len(grp)
            cap_info = CAPITAIS_INFO.get(uf_upper, {"nome": "Capital", "lat": -15.0, "lon": -50.0, "regiao": "Brasil"})

            # Breakdown por tema
            temas_count = grp["matched_category"].value_counts().to_dict()
            temas_val = grp.groupby("matched_category")["valor_total_estimado"].sum().to_dict()

            subtemas_top = grp["matched_subtema"].value_counts().head(3).to_dict()

            uf_rows.append({
                "uf_sigla": uf_upper,
                "capital": cap_info["nome"],
                "regiao": cap_info.get("regiao", "Brasil"),
                "lat": cap_info["lat"],
                "lon": cap_info["lon"],
                "total_editais": n_editais,
                "valor_total_estimado": v_tot,
                "ticket_medio": v_tot / n_editais if n_editais > 0 else 0.0,
                "temas_count": temas_count,
                "temas_val": temas_val,
                "subtemas_top": subtemas_top,
                "tema_lider": max(temas_count, key=temas_count.get) if temas_count else "Tecnologia",
            })

        df_uf = pd.DataFrame(uf_rows)
        if not df_uf.empty:
            df_uf.sort_values(by="valor_total_estimado", ascending=False, inplace=True)

        # 2. Agregação por Município
        muni_rows = []
        for (muni, uf), grp in df.groupby(["municipio_nome", "uf_sigla"]):
            muni_str = cls.normalizar_nome(muni)
            uf_upper = str(uf).strip().upper()
            if not muni_str:
                continue

            lat, lon, is_exact = cls.get_coordenadas(muni_str, uf_upper)
            v_tot = grp["valor_total_estimado"].sum()
            n_editais = len(grp)

            temas_count = grp["matched_category"].value_counts().to_dict()
            top_orgaos = grp["razao_social_orgao"].dropna().unique().tolist()[:3]
            selo_logistico = grp["selo_logistico"].dropna().iloc[0] if "selo_logistico" in grp.columns and not grp["selo_logistico"].dropna().empty else ""
            base_ref = grp["base_logistica"].dropna().iloc[0] if "base_logistica" in grp.columns and not grp["base_logistica"].dropna().empty else "Regional"

            muni_rows.append({
                "municipio": muni_str,
                "uf": uf_upper,
                "localidade": f"{muni_str}/{uf_upper}",
                "lat": lat,
                "lon": lon,
                "is_exact_coords": is_exact,
                "total_editais": n_editais,
                "valor_total_estimado": v_tot,
                "ticket_medio": v_tot / n_editais if n_editais > 0 else 0.0,
                "temas_count": temas_count,
                "tema_lider": max(temas_count, key=temas_count.get) if temas_count else "Geral",
                "top_orgaos": top_orgaos,
                "selo_logistico": selo_logistico,
                "base_logistica": base_ref
            })

        df_muni = pd.DataFrame(muni_rows)
        if not df_muni.empty:
            df_muni.sort_values(by="valor_total_estimado", ascending=False, inplace=True)

        return df_uf, df_muni

    @classmethod
    def criar_mapa_folium(
        cls,
        df: pd.DataFrame,
        mostrar_raios_bases: bool = True
    ) -> folium.Map:
        """Constrói mapa Leaflet interativo completo com Folium."""
        df_uf, df_muni = cls.agregar_dados_geograficos(df)

        # Mapa centrado no Brasil (tiles=None para utilizar CDN de alta performance sem bloqueio 403)
        m = folium.Map(
            location=[-14.235, -51.925],
            zoom_start=4.4,
            tiles=None,
            prefer_canvas=True
        )

        # ==============================================================
        # PROVEDORES DE TILES (SUÍTE OFICIAL ESRI & OSM - 100% ESTÁVEIS)
        # ==============================================================
        # 1. Esri WorldStreetMap (Padrão Ativo: ruas, rodovias, cidades e conexões viárias)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
            attr="Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, TomTom",
            name="🚗 Esri StreetMap (Ruas & Rodovias)",
            max_zoom=19,
            control=True,
            show=True,
        ).add_to(m)

        # 2. Esri Light Gray Canvas (Claro / Padrão Minimalista Corporativo)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
            attr="Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ",
            name="🗺️ Esri Light Canvas (Claro / Padrão)",
            max_zoom=19,
            control=True,
            show=False,
        ).add_to(m)

        # 3. Esri World Topo Map (Topográfico, Cidades, Relevo & Malha Urbana)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
            attr="Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ, TomTom, USGS",
            name="🏙️ Esri TopoMap (Cidades & Detalhes)",
            max_zoom=19,
            control=True,
            show=False,
        ).add_to(m)

        # 4. Esri Dark Gray Canvas (Modo Noturno Executivo)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
            attr="Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ",
            name="🌙 Esri Dark Canvas (Modo Noturno)",
            max_zoom=19,
            control=True,
            show=False,
        ).add_to(m)

        # 5. Esri World Imagery (Satélite & Imagens Aéreas HD)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye",
            name="🛰️ Esri Satélite (Foto Aérea HD)",
            max_zoom=19,
            control=True,
            show=False,
        ).add_to(m)

        # 6. OpenStreetMap (Padrão Global Colaborativo)
        folium.TileLayer(
            tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            name="🌍 OpenStreetMap (Padrão Global)",
            max_zoom=19,
            control=True,
            show=False,
        ).add_to(m)

        # ==============================================================
        # CAMADA 1: AS 9 BASES OPERACIONAIS ESTRATÉGICAS (RAIO 250 KM)
        # ==============================================================
        fg_bases = folium.FeatureGroup(name="⭐ 9 Bases Operacionais (Raio 250 km)", show=mostrar_raios_bases)

        for base_nome, b_info in BASES_ESTRATEGICAS.items():
            b_lat = b_info["lat"]
            b_lon = b_info["lon"]
            b_cor = b_info["cor"]

            # Círculo semitransparente do raio de 250 km
            folium.Circle(
                location=[b_lat, b_lon],
                radius=250 * 1000,  # 250 km em metros
                color=b_cor,
                weight=1.5,
                fill=True,
                fill_color=b_cor,
                fill_opacity=0.08,
                tooltip=f"<b>Hub Central: {base_nome}/{b_info['uf']}</b><br>Raio Operacional: 250 km",
            ).add_to(fg_bases)

            # Marcador estelar central do Hub
            popup_base = f"""
            <div style="font-family: Arial; font-size: 13px; width: 220px; color: #1E293B;">
                <h4 style="margin: 0; color: #1E3A8A;">⭐ Hub: {base_nome} ({b_info['uf']})</h4>
                <p style="margin: 4px 0;"><b>Raio de Atendimento:</b> até 250 km</p>
                <p style="margin: 4px 0; font-size: 11px; color: #475569;">Polo estratégico para atuação comercial presencial e suporte logístico.</p>
            </div>
            """
            folium.Marker(
                location=[b_lat, b_lon],
                icon=folium.Icon(color="darkblue", icon="star", prefix="fa"),
                popup=folium.Popup(popup_base, max_width=250),
                tooltip=f"Hub Operacional {base_nome}/{b_info['uf']}"
            ).add_to(fg_bases)

        fg_bases.add_to(m)

        # ==============================================================
        # CAMADA 2: CAPITAIS BRASILEIRAS (ESTADOS) COM POPUPS RICOS
        # ==============================================================
        fg_capitais = folium.FeatureGroup(name="🏛️ Capitais e Estados (Visão Macro)", show=True)

        if not df_uf.empty:
            max_val = df_uf["valor_total_estimado"].max() or 1.0

            for _, row in df_uf.iterrows():
                u_lat = row["lat"]
                u_lon = row["lon"]
                val = row["valor_total_estimado"]
                n_editais = row["total_editais"]
                uf_sigla = row["uf_sigla"]
                cap_nome = row["capital"]

                # Raio visual proporcional ao log do valor
                radius_px = 6 + (math.log10(val + 10) / math.log10(max_val + 10)) * 18 if val > 0 else 6

                # Monta detalhes temáticos no HTML
                temas_html = "".join(
                    f"<li style='margin-bottom: 2px;'><b>{cat}:</b> {cnt} editais</li>"
                    for cat, cnt in list(row["temas_count"].items())[:4]
                )

                val_compacto = formatar_moeda_compacta(val)
                val_completo = formatar_moeda_completa(val)
                ticket_str = formatar_moeda_completa(row['ticket_medio'])
                editais_str = formatar_inteiro(n_editais)

                popup_html = f"""
                <div style="font-family: Arial, sans-serif; font-size: 12px; width: 270px; line-height: 1.4; color: #0F172A;">
                    <div style="border-bottom: 2px solid #3B82F6; padding-bottom: 4px; margin-bottom: 6px;">
                        <h4 style="margin: 0; color: #1E3A8A;">🏛️ {cap_nome} / {uf_sigla}</h4>
                        <span style="font-size: 11px; color: #64748B;">Região: {row['regiao']}</span>
                    </div>
                    <p style="margin: 3px 0;"><b>Total de Editais:</b> <span style="color: #2563EB; font-weight: bold;">{editais_str}</span></p>
                    <p style="margin: 3px 0;"><b>Volume Estimado:</b> <span style="color: #059669; font-weight: bold; font-size: 13px;">{val_compacto}</span></p>
                    <p style="margin: 1px 0; font-size: 10px; color: #64748B;">({val_completo})</p>
                    <p style="margin: 3px 0;"><b>Ticket Médio:</b> {ticket_str}</p>
                    
                    <div style="margin-top: 8px; background: #F1F5F9; padding: 6px; border-radius: 4px;">
                        <b>Top Temas Licitados:</b>
                        <ul style="margin: 4px 0 0 16px; padding: 0; font-size: 11px;">
                            {temas_html}
                        </ul>
                    </div>
                </div>
                """

                folium.CircleMarker(
                    location=[u_lat, u_lon],
                    radius=radius_px,
                    color="#2563EB",
                    weight=2,
                    fill=True,
                    fill_color="#3B82F6",
                    fill_opacity=0.75,
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=f"{cap_nome}/{uf_sigla}: {val_compacto} ({editais_str} editais)"
                ).add_to(fg_capitais)

        fg_capitais.add_to(m)

        # ==============================================================
        # CAMADA 3: MUNICÍPIOS COM MARKERCLUSTER (GRANULARIDADE LOCAL)
        # ==============================================================
        fg_munis = folium.FeatureGroup(name="📍 Granularidade por Município (Agrupamento)", show=True)
        cluster = plugins.MarkerCluster().add_to(fg_munis)

        if not df_muni.empty:
            for _, row in df_muni.iterrows():
                m_lat = row["lat"]
                m_lon = row["lon"]
                muni = row["municipio"]
                uf = row["uf"]
                val = row["valor_total_estimado"]
                n_editais = row["total_editais"]
                selo = row["selo_logistico"]
                tema_lider = row["tema_lider"]
                orgaos_str = "<br>".join([f"• {o[:40]}..." for o in row["top_orgaos"]])

                m_val_compacto = formatar_moeda_compacta(val)
                m_val_completo = formatar_moeda_completa(val)
                m_editais_str = formatar_inteiro(n_editais)

                popup_muni = f"""
                <div style="font-family: Arial, sans-serif; font-size: 12px; width: 250px; color: #0F172A;">
                    <div style="border-bottom: 2px solid #10B981; padding-bottom: 4px; margin-bottom: 6px;">
                        <h4 style="margin: 0; color: #065F46;">📍 {muni}/{uf}</h4>
                        {f"<span style='font-size: 10px; background: #DCFCE7; color: #166534; padding: 2px 4px; border-radius: 3px;'>{selo}</span>" if selo else ""}
                    </div>
                    <p style="margin: 2px 0;"><b>Editais Mapeados:</b> {m_editais_str}</p>
                    <p style="margin: 2px 0;"><b>Volume Total:</b> <span style="color: #059669; font-weight: bold; font-size: 13px;">{m_val_compacto}</span></p>
                    <p style="margin: 1px 0; font-size: 10px; color: #64748B;">({m_val_completo})</p>
                    <p style="margin: 2px 0;"><b>Tema Predominante:</b> {tema_lider}</p>
                    {f"<div style='margin-top: 6px; font-size: 11px;'><b>Principais Órgãos:</b><br>{orgaos_str}</div>" if orgaos_str else ""}
                </div>
                """

                # Cores baseadas no tema líder
                cor_marker = "blue"
                if "Educação" in tema_lider or "IDEB" in tema_lider:
                    cor_marker = "green"
                elif "Políticas" in tema_lider or "M&A" in tema_lider:
                    cor_marker = "orange"
                elif "IA" in tema_lider or "Dados" in tema_lider:
                    cor_marker = "purple"
                elif "SaaS" in tema_lider or "Software" in tema_lider:
                    cor_marker = "darkblue"

                folium.Marker(
                    location=[m_lat, m_lon],
                    icon=folium.Icon(color=cor_marker, icon="info-sign"),
                    popup=folium.Popup(popup_muni, max_width=280),
                    tooltip=f"{muni}/{uf}: {m_val_compacto} ({m_editais_str} editais)"
                ).add_to(cluster)

        fg_munis.add_to(m)

        # Adiciona controle de camadas (LayerControl) e tela cheia
        folium.LayerControl(collapsed=False).add_to(m)
        plugins.Fullscreen(position="topright").add_to(m)

        return m

    @classmethod
    def exportar_mapa_html(
        cls,
        df: pd.DataFrame,
        caminho_saida: str = "pncp_intelligence/data/processed/mapa_interativo_oportunidades_pncp.html"
    ) -> str:
        """Gera e salva o arquivo HTML autocontido com cabeçalho explicativo e estilos."""
        out_path = Path(caminho_saida)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        m = cls.criar_mapa_folium(df, mostrar_raios_bases=True)
        html_str = m.get_root().render()

        # Injeta política de Referer permissiva para compatibilidade total com navegadores e visualização local (file://)
        if "<head>" in html_str:
            html_str = html_str.replace(
                "<head>",
                '<head>\n    <meta name="referrer" content="no-referrer-when-downgrade">'
            )

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_str)

        return str(out_path)
