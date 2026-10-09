"""Exportador de dados analíticos para Excel multi-abas, Parquet e CSV.

Gera relatórios executivos estruturados para integração direta com BI,
planilhas de prospecção comercial e modelagem financeira.
"""

import re
from pathlib import Path
from typing import Optional
import pandas as pd
from pncp_intelligence.src.analytics import PNCPAnalytics


def sanitize_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    """Remove caracteres de controle XML que causam IllegalCharacterError no openpyxl."""
    if df.empty:
        return df
    clean_df = df.copy()
    for col in clean_df.select_dtypes(include=["object"]).columns:
        clean_df[col] = clean_df[col].apply(
            lambda val: re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(val)) if pd.notna(val) else val
        )
    return clean_df


class PNCPExporter:
    def __init__(self, analytics: Optional[PNCPAnalytics] = None, output_dir: str = "pncp_intelligence/data/processed"):
        self.analytics = analytics or PNCPAnalytics()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(self, file_prefix: str = "pncp_mercado") -> dict[str, str]:
        """Exporta a base consolidada para Excel multi-abas, Parquet e CSV."""
        df_editais = self.analytics.get_dataframe()
        df_itens = self.analytics.get_itens_dataframe()

        excel_path = self.output_dir / f"{file_prefix}_analise_completa.xlsx"
        parquet_editais_path = self.output_dir / f"{file_prefix}_editais.parquet"
        parquet_itens_path = self.output_dir / f"{file_prefix}_itens.parquet"
        csv_path = self.output_dir / f"{file_prefix}_editais.csv"

        # 1. Gera Excel com múltiplas visões analíticas sanitizadas
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            # Aba 1: Resumo Executivo e KPIs
            kpis = self.analytics.summary_kpis(df_editais)
            df_kpis = pd.DataFrame(list(kpis.items()), columns=["Indicador", "Valor"])
            df_kpis.to_excel(writer, sheet_name="Resumo_KPIs", index=False)

            # Aba 2: Editais de Interesse
            sanitize_for_excel(df_editais).to_excel(writer, sheet_name="Editais", index=False)

            # Aba 3: Itens Detalhados
            if not df_itens.empty:
                sanitize_for_excel(df_itens).to_excel(writer, sheet_name="Itens_Detalhados", index=False)

            # Aba 4: Radar de Oportunidades
            df_radar = self.analytics.live_opportunities(df_editais)
            if not df_radar.empty:
                sanitize_for_excel(df_radar).to_excel(writer, sheet_name="Radar_Oportunidades", index=False)

            # Aba 5: Análise Temática (Subtemas)
            df_temas = self.analytics.thematic_breakdown(df_editais)
            if not df_temas.empty:
                sanitize_for_excel(df_temas).to_excel(writer, sheet_name="Analise_Tematica", index=False)

            # Aba 6: Top Órgãos Compradores
            df_orgaos = self.analytics.top_orgaos(df_editais, top_n=30)
            if not df_orgaos.empty:
                sanitize_for_excel(df_orgaos).to_excel(writer, sheet_name="Top_Orgaos", index=False)

            # Aba 7: Distribuição Geográfica (UF)
            df_uf = self.analytics.geographic_distribution(df_editais)
            if not df_uf.empty:
                sanitize_for_excel(df_uf).to_excel(writer, sheet_name="Distribuicao_UF", index=False)

            # Aba 8: As 7 Bases Operacionais Estratégicas
            df_base = self.analytics.logistics_breakdown(df_editais)
            if not df_base.empty:
                sanitize_for_excel(df_base).to_excel(writer, sheet_name="Bases_Logisticas", index=False)

        # 2. Exporta Parquet para velocidade analítica
        if not df_editais.empty:
            df_editais.to_parquet(parquet_editais_path, index=False)
            df_editais.to_csv(csv_path, index=False, encoding="utf-8-sig")

        if not df_itens.empty:
            df_itens.to_parquet(parquet_itens_path, index=False)

        return {
            "excel": str(excel_path),
            "parquet_editais": str(parquet_editais_path),
            "parquet_itens": str(parquet_itens_path),
            "csv": str(csv_path),
        }
