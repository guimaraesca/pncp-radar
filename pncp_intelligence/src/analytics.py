"""Motor de análise quantitativa, inteligência temática e radar de oportunidades.

Processa os dados consolidados no SQLite e extrai indicadores de mercado,
sazonalidade, rankings de compradores e segmentações temáticas.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd
from pncp_intelligence.src.db import PNCPDatabase


class PNCPAnalytics:
    def __init__(self, db: Optional[PNCPDatabase] = None):
        self.db = db or PNCPDatabase()

    def get_dataframe(self) -> pd.DataFrame:
        """Carrega todos os editais coletados em um DataFrame do Pandas."""
        with self.db.get_connection() as conn:
            df = pd.read_sql_query("""
                SELECT 
                    id, numero_controle_pncp, ano_compra, numero_compra, processo,
                    cnpj_orgao, razao_social_orgao, esfera_id, poder_id,
                    uf_sigla, municipio_nome, nome_unidade,
                    modalidade_id, modalidade_nome, modo_disputa_nome, situacao_compra_nome,
                    srp, objeto_compra, informacao_complementar,
                    valor_total_estimado, valor_total_homologado,
                    data_publicacao_pncp, data_abertura_proposta, data_encerramento_proposta,
                    link_sistema_origem, link_processo_eletronico,
                    matched_category, matched_subtema, matched_keywords,
                    base_logistica, distancia_km, faixa_raio, selo_logistico, is_priority_geo,
                    briefing_ia_path, pdf_paths
                FROM contratacoes
            """, conn)

        if not df.empty:
            df["data_publicacao_pncp"] = pd.to_datetime(df["data_publicacao_pncp"], errors="coerce")
            df["valor_total_estimado"] = pd.to_numeric(df["valor_total_estimado"], errors="coerce").fillna(0.0)
            df["valor_total_homologado"] = pd.to_numeric(df["valor_total_homologado"], errors="coerce").fillna(0.0)

            # --- HIGIENIZAÇÃO DE ANOMALIAS DE DIGITAÇÃO DO PNCP ---
            # 1. Se valor homologado existe e estimado for aberrante (>50x e >R$ 50 mi), corrige pelo valor homologado
            mask_typo = (df["valor_total_homologado"] > 0) & (df["valor_total_estimado"] > df["valor_total_homologado"] * 50) & (df["valor_total_estimado"] > 50_000_000)
            df.loc[mask_typo, "valor_total_estimado"] = df.loc[mask_typo, "valor_total_homologado"]

            # 2. Dispensas de licitação com valores irreais (> R$ 10 mi digitados por engano pelo órgão)
            is_dispensa = df["modalidade_nome"].fillna("").astype(str).str.lower().str.contains("dispensa")
            mask_dispensa_outlier = is_dispensa & (df["valor_total_estimado"] > 10_000_000)
            df.loc[mask_dispensa_outlier, "valor_total_estimado"] = df.loc[mask_dispensa_outlier, "valor_total_homologado"].replace(0, 100_000.0)

            # 3. Trava de segurança para valores astronômicos (> R$ 2 bilhões exceto com homologado coerente)
            mask_absurdo = (df["valor_total_estimado"] > 2_000_000_000) & (df["valor_total_homologado"] > 0)
            df.loc[mask_absurdo, "valor_total_estimado"] = df.loc[mask_absurdo, "valor_total_homologado"]

            df["ano_mes_pub"] = df["data_publicacao_pncp"].dt.to_period("M").astype(str)
            df["distancia_km"] = pd.to_numeric(df["distancia_km"], errors="coerce").fillna(999.0)
            df["is_priority_geo"] = pd.to_numeric(df["is_priority_geo"], errors="coerce").fillna(0).astype(int)
        return df

    def get_itens_dataframe(self) -> pd.DataFrame:
        """Carrega todos os itens de contratações em um DataFrame."""
        with self.db.get_connection() as conn:
            df = pd.read_sql_query("""
                SELECT 
                    i.id, i.numero_controle_pncp, i.numero_item, i.descricao,
                    i.quantidade, i.unidade_medida, 
                    i.valor_unitario_estimado, i.valor_total_estimado,
                    i.valor_unitario_homologado, i.valor_total_homologado,
                    i.situacao_item_nome, i.criterio_julgamento_nome,
                    c.razao_social_orgao, c.uf_sigla, c.matched_category, c.matched_subtema
                FROM itens_contratacao i
                LEFT JOIN contratacoes c ON i.numero_controle_pncp = c.numero_controle_pncp
            """, conn)
        return df

    def summary_kpis(self, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Calcula os principais KPIs quantitativos de mercado."""
        if df is None:
            df = self.get_dataframe()

        if df.empty:
            return {
                "total_editais": 0,
                "valor_total_estimado": 0.0,
                "valor_total_homologado": 0.0,
                "ticket_medio": 0.0,
                "ticket_mediano": 0.0,
                "desagio_medio_pct": 0.0,
                "total_orgaos": 0,
                "total_ufs": 0,
            }

        total_editais = len(df)
        val_estimado = float(df["valor_total_estimado"].sum())
        val_homologado = float(df["valor_total_homologado"].sum())
        ticket_medio = float(df["valor_total_estimado"].mean()) if total_editais > 0 else 0.0
        ticket_mediano = float(df["valor_total_estimado"].median()) if total_editais > 0 else 0.0

        # Cálculo de deságio apenas onde houve homologação e valor estimado > 0
        homologados = df[(df["valor_total_homologado"] > 0) & (df["valor_total_estimado"] > 0)]
        if not homologados.empty:
            desagio = ((homologados["valor_total_estimado"] - homologados["valor_total_homologado"]) / homologados["valor_total_estimado"]) * 100
            desagio_medio = float(desagio.clip(lower=0, upper=95).mean())
        else:
            desagio_medio = 0.0

        return {
            "total_editais": total_editais,
            "valor_total_estimado": val_estimado,
            "valor_total_homologado": val_homologado,
            "ticket_medio": ticket_medio,
            "ticket_mediano": ticket_mediano,
            "desagio_medio_pct": desagio_medio,
            "total_orgaos": int(df["cnpj_orgao"].nunique()),
            "total_ufs": int(df["uf_sigla"].dropna().nunique()),
        }

    def temporal_evolution(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Sazonalidade e evolução mensal de editais e montante em R$."""
        if df is None:
            df = self.get_dataframe()
        if df.empty:
            return pd.DataFrame()

        grouped = df.groupby("ano_mes_pub").agg(
            qtd_editais=("id", "count"),
            valor_estimado_total=("valor_total_estimado", "sum"),
            ticket_medio=("valor_total_estimado", "mean"),
        ).reset_index().sort_values("ano_mes_pub")

        return grouped

    def top_orgaos(self, df: Optional[pd.DataFrame] = None, top_n: int = 20) -> pd.DataFrame:
        """Ranking dos órgãos públicos compradores com maior orçamento."""
        if df is None:
            df = self.get_dataframe()
        if df.empty:
            return pd.DataFrame()

        grouped = df.groupby(["razao_social_orgao", "uf_sigla"]).agg(
            qtd_editais=("id", "count"),
            valor_estimado_total=("valor_total_estimado", "sum"),
            ticket_medio=("valor_total_estimado", "mean"),
        ).reset_index().sort_values("valor_estimado_total", ascending=False).head(top_n)

        return grouped

    def geographic_distribution(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Volume de recursos e quantidade de editais distribuídos por estado (UF)."""
        if df is None:
            df = self.get_dataframe()
        if df.empty:
            return pd.DataFrame()

        grouped = df.groupby("uf_sigla").agg(
            qtd_editais=("id", "count"),
            valor_estimado_total=("valor_total_estimado", "sum"),
        ).reset_index().sort_values("valor_estimado_total", ascending=False)

        return grouped

    def thematic_breakdown(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Distribuição financeira e volumétrica por categoria e subtema."""
        if df is None:
            df = self.get_dataframe()
        if df.empty:
            return pd.DataFrame()

        grouped = df.groupby(["matched_category", "matched_subtema"]).agg(
            qtd_editais=("id", "count"),
            valor_estimado_total=("valor_total_estimado", "sum"),
            ticket_medio=("valor_total_estimado", "mean"),
        ).reset_index().sort_values("valor_estimado_total", ascending=False)

        return grouped

    def modalidade_distribution(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Distribuição por modalidade de licitação."""
        if df is None:
            df = self.get_dataframe()
        if df.empty:
            return pd.DataFrame()

        grouped = df.groupby("modalidade_nome").agg(
            qtd_editais=("id", "count"),
            valor_estimado_total=("valor_total_estimado", "sum"),
        ).reset_index().sort_values("qtd_editais", ascending=False)

        return grouped

    def logistics_breakdown(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Distribuição de oportunidades e recursos pelas 7 bases operacionais."""
        if df is None:
            df = self.get_dataframe()
        if df.empty or "base_logistica" not in df.columns:
            return pd.DataFrame()

        has_base = df[df["base_logistica"].notna() & (df["base_logistica"] != "") & (df["base_logistica"] != "Outro")]
        if has_base.empty:
            return pd.DataFrame()

        grouped = has_base.groupby(["base_logistica", "faixa_raio"]).agg(
            qtd_editais=("id", "count"),
            valor_estimado_total=("valor_total_estimado", "sum"),
        ).reset_index().sort_values("valor_estimado_total", ascending=False)

        return grouped

    def live_opportunities(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Retorna oportunidades ativas com prazo de envio de propostas em aberto, priorizadas por logística."""
        if df is None:
            df = self.get_dataframe()
        if df.empty:
            return pd.DataFrame()

        now_str = datetime.now().isoformat()
        mask = (df["data_encerramento_proposta"].isna()) | (df["data_encerramento_proposta"] >= now_str)
        active = df[mask].copy()

        # Priorização logística na fila: Bases estratégicas primeiro, menores distâncias, maiores valores
        if "is_priority_geo" in active.columns and "distancia_km" in active.columns:
            active = active.sort_values(
                by=["is_priority_geo", "distancia_km", "valor_total_estimado"],
                ascending=[False, True, False]
            )
        else:
            active = active.sort_values("valor_total_estimado", ascending=False)

        return active

    def live_candidacy_radar(
        self,
        df: Optional[pd.DataFrame] = None,
        peso_aderencia: float = 35.0,
        peso_custo_beneficio: float = 25.0,
        peso_logistica: float = 25.0,
        peso_historico: float = 15.0,
    ) -> pd.DataFrame:
        """Processa editais abertos com motor de decisão Datadriven em 4 pilares: Aderência, Custo-Benefício, Logística e Histórico."""
        if df is None:
            df = self.get_dataframe()
        if df.empty:
            return pd.DataFrame()

        now = datetime.now()
        now_iso = now.isoformat()
        now_date_str = now.strftime("%Y-%m-%d")

        df_copy = df.copy()

        # Filtra editais com prazo em aberto (encerramento futuro ou abertura futura)
        mask_aberto = (
            (df_copy["data_encerramento_proposta"].notna()) & (df_copy["data_encerramento_proposta"] >= now_iso)
        ) | (
            (df_copy["data_encerramento_proposta"].isna()) & (df_copy["data_abertura_proposta"].notna()) & (df_copy["data_abertura_proposta"] >= now_date_str)
        )

        abertos = df_copy[mask_aberto].copy()
        if abertos.empty:
            return pd.DataFrame()

        def calcular_metricas(row):
            motivos = []

            # -------------------------------------------------------------
            # PILAR 1: ADERÊNCIA TÉCNICA (0 a 100 pts)
            # -------------------------------------------------------------
            subtema = str(row.get("matched_subtema", "")).lower()
            objeto = str(row.get("objeto_compra", "")).lower()
            
            prio_tech = ["software", "cloud", "saas", "dados", "ia", "inteligência", "plataforma", "ideb", "avaliação", "robótica", "maker", "bncc", "computação", "simulado", "enem"]
            if any(t in subtema or t in objeto for t in prio_tech):
                s_aderencia = 100
                motivos.append("🎯 Alta Aderência (Tecnologia/Educação)")
            elif any(t in subtema or t in objeto for t in ["consultoria", "capacitação", "formação", "planejamento", "gestão escolar"]):
                s_aderencia = 80
                motivos.append("📘 Aderência Moderada (Consultoria/Gestão)")
            elif any(t in subtema or t in objeto for t in ["assessoria", "pesquisa", "diagnóstico"]):
                s_aderencia = 65
                motivos.append("📑 Aderência Específica (Pesquisa/Estudo)")
            else:
                s_aderencia = 50
                motivos.append("📄 Aderência Geral")

            # -------------------------------------------------------------
            # PILAR 2: CUSTO-BENEFÍCIO & MARGEM (0 a 100 pts)
            # -------------------------------------------------------------
            val = float(row.get("valor_total_estimado", 0) or 0)
            if 50_000 <= val <= 1_500_000:
                s_custo = 100
                motivos.append("💰 Ticket Sweet Spot (R$ 50k - 1,5M)")
            elif 1_500_000 < val <= 5_000_000:
                s_custo = 85
                motivos.append("💰 Médio-Alto Porte (R$ 1,5M - 5M)")
            elif val > 5_000_000:
                s_custo = 70
                motivos.append("🏢 Enterprise / Grande Porte")
            elif val > 0:
                s_custo = 75
                motivos.append("⚡ Ticket Ágil (< R$ 50k)")
            else:
                s_custo = 60
                motivos.append("Valor sob Demanda")

            # Ajuste de prazo restante na margem de execução
            dt_limite_str = row.get("data_encerramento_proposta") or row.get("data_abertura_proposta")
            dias_restantes = 0.0
            if pd.notna(dt_limite_str):
                try:
                    dt = pd.to_datetime(dt_limite_str)
                    dias_restantes = max(0.0, (dt - now).total_seconds() / 86400.0)
                except Exception:
                    dias_restantes = 0.0

            if dias_restantes >= 7.0:
                s_custo = min(100, s_custo + 5)
                motivos.append(f"⏳ Janela Confortável ({int(dias_restantes)}d)")
            elif dias_restantes < 2.0:
                s_custo = max(20, s_custo - 15)
                motivos.append("🚨 Prazo Urgente (< 48h)")

            # -------------------------------------------------------------
            # PILAR 3: LOGÍSTICA & OPERAÇÃO (0 a 100 pts)
            # -------------------------------------------------------------
            base = str(row.get("base_logistica", "")).lower()
            dist = float(row.get("distancia_km", 999) or 999)
            is_prio = int(row.get("is_priority_geo", 0) or 0)

            if "remoto" in base or any(t in subtema for t in ["software", "cloud", "saas", "dados", "ia"]):
                s_logistica = 100
                motivos.append("💻 100% Remoto / Nuvem")
            elif dist <= 100 or is_prio == 1:
                s_logistica = 95
                motivos.append(f"📍 Base Próxima ({int(dist)} km)")
            elif dist <= 250:
                s_logistica = 80
                motivos.append(f"🚗 Raio 250 km ({int(dist)} km)")
            elif dist <= 500:
                s_logistica = 55
                motivos.append("🗺️ Médio Raio (até 500 km)")
            else:
                s_logistica = 35
                motivos.append("Fora da Malha Direta")

            # -------------------------------------------------------------
            # PILAR 4: HISTÓRICO & FRICÇÃO DO ÓRGÃO (0 a 100 pts)
            # -------------------------------------------------------------
            mod = str(row.get("modalidade_nome", "")).lower()
            if "dispensa" in mod:
                s_historico = 100
                motivos.append("⚡ Dispensa Eletrônica (Baixa Fricção)")
            elif "credenciamento" in mod or "inexigibilidade" in mod:
                s_historico = 90
                motivos.append("📜 Credenciamento / Inexigibilidade")
            elif "pregão" in mod:
                s_historico = 75
                motivos.append("🏛️ Pregão Eletrônico")
            else:
                s_historico = 60
                motivos.append("🏛️ Concorrência / Outros")

            # -------------------------------------------------------------
            # SCORE PONDERADO TOTAL (0 a 100 pts)
            # -------------------------------------------------------------
            peso_tot = max(1.0, float(peso_aderencia) + float(peso_custo_beneficio) + float(peso_logistica) + float(peso_historico))
            score_final = int(round(
                (s_aderencia * peso_aderencia +
                 s_custo * peso_custo_beneficio +
                 s_logistica * peso_logistica +
                 s_historico * peso_historico) / peso_tot
            ))
            score_final = max(0, min(100, score_final))

            # Classificação Executiva
            if score_final >= 75:
                decisao = "🟢 GO"
                nivel = "🟢 Alta Recomendação"
                badge = "ALTA RECOMENDAÇÃO"
            elif score_final >= 50:
                decisao = "🟡 WATCH"
                nivel = "🟡 Candidatura Viável"
                badge = "VIÁVEL"
            else:
                decisao = "🔴 NO-GO"
                nivel = "🔴 Baixa Prioridade"
                badge = "AVALIAR"

            pncp_id = str(row.get("numero_controle_pncp", "")).strip()
            url_oficial = row.get("link_sistema_origem") or f"https://pncp.gov.br/app/editais/{pncp_id}"

            return (
                score_final, s_aderencia, s_custo, s_logistica, s_historico,
                decisao, nivel, badge, dias_restantes, " • ".join(motivos), url_oficial
            )

        resultados = abertos.apply(calcular_metricas, axis=1)
        abertos["score_candidatura"] = [r[0] for r in resultados]
        abertos["score_aderencia"] = [r[1] for r in resultados]
        abertos["score_custo_beneficio"] = [r[2] for r in resultados]
        abertos["score_logistica"] = [r[3] for r in resultados]
        abertos["score_historico"] = [r[4] for r in resultados]
        abertos["decisao_tag"] = [r[5] for r in resultados]
        abertos["nivel_recomendacao"] = [r[6] for r in resultados]
        abertos["badge_recomendacao"] = [r[7] for r in resultados]
        abertos["dias_restantes"] = [r[8] for r in resultados]
        abertos["justificativa_candidatura"] = [r[9] for r in resultados]
        abertos["url_oficial_edital"] = [r[10] for r in resultados]

        return abertos.sort_values(by=["score_candidatura", "valor_total_estimado"], ascending=[False, False])
