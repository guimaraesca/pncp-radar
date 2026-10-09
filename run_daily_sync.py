#!/usr/bin/env python3
"""Script de Sincronização Diária & Disparo de Alertas PNCP.

Executa:
1. Coleta das oportunidades com envio de proposta em aberto hoje.
2. Atualização dos scores de candidatura (0 a 100).
3. Reexportação das planilhas Excel/Parquet e do mapa HTML interativo.
4. Envio do briefing executivo no Telegram para tomada de decisão rápida.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Carrega .env manualmente caso python-dotenv não esteja instalado
env_file = Path(__file__).resolve().parent / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip("'\"")

# Insere diretório no sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pncp_intelligence.src.analytics import PNCPAnalytics
from pncp_intelligence.src.collector import PNCPCollector
from pncp_intelligence.src.db import PNCPDatabase
from pncp_intelligence.src.exporter import PNCPExporter
from pncp_intelligence.src.geo_map import GeoMapBuilder
from pncp_intelligence.src.telegram_bot import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(__file__).resolve().parent / "daily_sync.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("DailySync")


def main():
    logger.info("==================================================================")
    logger.info("🚀 INICIANDO ROTINA DIÁRIA DE INTELIGÊNCIA PNCP")
    logger.info(f"🕒 Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("==================================================================")

    db = PNCPDatabase()
    analytics = PNCPAnalytics(db)
    collector = PNCPCollector(db=db)
    exporter = PNCPExporter(analytics)
    telegram = TelegramNotifier()

    # 1. Coleta de Oportunidades Vivas (Próximos 30 dias)
    logger.info("📡 1. Verificando propostas abertas no PNCP para os temas prioritários...")
    try:
        novos = collector.collect_live_opportunities(days_ahead=30, max_pages_per_mod=10)
        logger.info(f"✅ Coleta finalizada: {len(novos)} editais com propostas abertas mapeados.")
    except Exception as e:
        logger.error(f"⚠️ Erro ao consultar API ao vivo do PNCP: {e}")

    # 2. Carrega base consolidada e calcula Radar de Candidatura
    logger.info("🎯 2. Calculando Scores de Candidatura (Fit Logístico, Prazo, Modalidade e Ticket)...")
    df_geral = analytics.get_dataframe()
    df_radar = analytics.live_candidacy_radar(df_geral)
    total_abertos = len(df_radar)
    top_picks = (df_radar["score_candidatura"] >= 75).sum() if not df_radar.empty else 0
    logger.info(f"📊 {total_abertos} editais abertos identificados ({top_picks} com Score ≥ 75).")

    # 3. Reexportação de Relatórios e Mapa Interativo
    logger.info("📁 3. Atualizando planilhas e mapas interativos...")
    try:
        paths = exporter.export_all()
        logger.info(f"✅ Excel atualizado: {paths['excel']}")
    except Exception as e:
        logger.error(f"⚠️ Erro ao exportar Excel: {e}")

    try:
        mapa_path = GeoMapBuilder.exportar_mapa_html(df_geral, "pncp_intelligence/data/processed/mapa_interativo_oportunidades_pncp.html")
        GeoMapBuilder.exportar_mapa_html(df_geral, "docs/index.html")
        logger.info(f"✅ Mapa Interativo Esri atualizado: {mapa_path}")
    except Exception as e:
        logger.error(f"⚠️ Erro ao reexportar mapa: {e}")

    # 4. Disparo de Briefing no Telegram
    logger.info("📱 4. Processando notificação para o Telegram...")
    if telegram.is_configured:
        sucesso = telegram.send_candidacy_alert(df_radar, top_n=6, total_indexados=len(df_geral))
        if sucesso:
            logger.info("✅ Briefing executivo enviado com sucesso para o seu Telegram!")
        else:
            logger.warning("⚠️ Falha ao entregar mensagem no Telegram. Verifique logs acima.")
    else:
        logger.info(
            "ℹ️ Telegram não configurado no .env. "
            "Para receber alertas diários, adicione TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID."
        )

    logger.info("==================================================================")
    logger.info("🎉 ROTINA DIÁRIA CONCLUÍDA COM SUCESSO!")
    logger.info("==================================================================")


if __name__ == "__main__":
    main()
