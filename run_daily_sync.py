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
from pncp_intelligence.src.observability import RunTracker, evaluate_health, persist_report
from pncp_intelligence.src.rematch import rematch_stale
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
    tracker = RunTracker(db, trigger=os.getenv("GITHUB_EVENT_NAME", "manual"))
    collector.run_id = tracker.start(keywords_hash=collector.matcher.fingerprint())
    logger.info(f"🧾 Execução {collector.run_id} (dicionário {collector.matcher.fingerprint()})")

    logger.info("📡 1. Verificando propostas abertas no PNCP (Busca Indexada por Termos + Varredura Ativa)...")
    novos = []
    run_error = None
    try:
        novos_search = collector.collect_by_search_terms(status="recebendo_proposta", max_pages_per_query=2)
        novos_live = collector.collect_live_opportunities(days_ahead=30, max_pages_per_mod=6)
        seen_ids = set()
        for op in novos_search + novos_live:
            if op.get("id") and op["id"] not in seen_ids:
                seen_ids.add(op["id"])
                novos.append(op)
        logger.info(
            f"✅ Coleta finalizada: {len(novos)} editais únicos com propostas abertas mapeados "
            f"({len(novos_search)} via busca textual, {len(novos_live)} via listagem geral)."
        )
    except Exception as e:
        run_error = f"{type(e).__name__}: {e}"
        logger.error(f"⚠️ Erro ao consultar API ao vivo do PNCP: {e}")

    # 1b. Reclassifica o que ficou com dicionário antigo (idempotente) e fecha o registro da execução
    try:
        rm = rematch_stale(db, collector.matcher)
        if rm["reprocessed"]:
            logger.info(f"🔁 Rematch: {rm['reprocessed']} linhas (+{rm['gained']} / -{rm['lost']}).")
    except Exception as e:
        run_error = run_error or f"rematch: {type(e).__name__}: {e}"
        logger.error(f"⚠️ Erro no rematch: {e}")

    run_status = tracker.finish(
        audits=collector.audits,
        rows_scanned=sum(a.records for a in collector.audits.values()),
        rows_matched=len(novos),
        api_errors=collector.api_errors,
        failed_chunks=collector.failed_chunks,
        error=run_error,
    )
    logger.info(f"🧾 Execução {collector.run_id} encerrada: {run_status}")

    # 1c. Observabilidade: 5 pilares (Freshness, Volume, Distribution, Schema, Lineage)
    report = evaluate_health(str(db.db_path))
    persist_report(str(db.db_path), report, collector.run_id)
    logger.info(f"🩺 Saúde dos dados: {report.overall} {report.counts()} | por pilar: {report.by_pillar()}")
    for r in report.results:
        if r.status in ("WARN", "FAIL"):
            logger.log(logging.ERROR if r.status == "FAIL" else logging.WARNING,
                       f"   [{r.status}] {r.pillar}/{r.name}: {r.observed} (esperado {r.expected}) {r.detail}")

    # 2. Carrega base consolidada e calcula Radar de Candidatura
    logger.info("🎯 2. Calculando Scores de Candidatura (Fit Logístico, Prazo, Modalidade e Ticket)...")
    df_geral = analytics.get_dataframe()
    # Escopo do negócio: só editais com match no perfil (o dashboard aplica o mesmo filtro)
    df_geral = df_geral[df_geral["matched_category"].notna() & (df_geral["matched_category"] != "")]
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

    # 4. Disparo de Briefing Unificado no Telegram (PNCP + I.C.A.R.O.)
    logger.info("📱 4. Processando Briefing Integrado no Telegram (PNCP + I.C.A.R.O.)...")
    if report.overall == "FAIL":
        logger.error("⛔ Saúde dos dados em FAIL: alerta de oportunidades NÃO enviado (evita decisão sobre dado ruim).")
    elif telegram.is_configured:
        import json
        icaro_opps = []
        icaro_json_paths = [
            Path(__file__).resolve().parent / "pncp_intelligence" / "data" / "icaro" / "oportunidades_icaro.json",
            Path(__file__).resolve().parent.parent / "SixSigma" / "data" / "db" / "oportunidades_icaro.json",
        ]
        for p in icaro_json_paths:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        icaro_opps = json.load(f)
                    break
                except Exception:
                    pass

        sucesso = telegram.send_integrated_briefing(df_radar, icaro_opps, top_pncp=6, top_icaro=6)
        if sucesso:
            logger.info("✅ Briefing executivo integrado enviado com sucesso para o seu Telegram!")
        else:
            logger.warning("⚠️ Falha ao entregar mensagem no Telegram. Verifique logs acima.")
    else:
        logger.info(
            "ℹ️ Telegram não configurado no .env. "
            "Para receber alertas diários, adicione TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID."
        )

    logger.info("==================================================================")
    if report.overall == "FAIL":
        logger.error("❌ ROTINA CONCLUÍDA COM FALHAS DE QUALIDADE DE DADOS (veja os [FAIL] acima).")
    else:
        logger.info(f"🎉 ROTINA DIÁRIA CONCLUÍDA (execução {run_status}, saúde {report.overall}).")
    logger.info("==================================================================")
    return 1 if report.overall == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
