#!/usr/bin/env python3
"""I.C.A.R.O. — Inteligência de Captura e Análise de Recrutamentos e Oportunidades
===================================================================================
Orquestrador Central e CLI Unificado.

Integra:
1. Vertente B2G / Compras Públicas: Motor PNCP Radar (Lei 14.133/2021).
2. Vertente Multilateral & Privada: Scrapers de Agências (UNESCO, PNUD, OEI),
   Fundações (Lemann, Unibanco) e Mercado Privado (EdTechs, GovTechs).
3. Análise Semântica via IA: Google Gemini calibrado para o perfil executivo.
4. Exportações & Visualização: Excel multi-abas, Parquet, Mapa Esri e Dashboard Streamlit.
5. Notificação Executiva: Briefing Diário Unificado e estruturado no Telegram.

Uso:
    python run_icaro.py                  # Ciclo diário completo integrado
    python run_icaro.py --mode pncp      # Apenas licitações e pregões PNCP
    python run_icaro.py --mode scrapers  # Apenas agências multilaterais e terceiro setor
    python run_icaro.py --mode dashboard # Inicializa o painel web Streamlit
    python run_icaro.py --mode export    # Apenas regera planilhas Excel e mapas
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ajusta limite de descritores de arquivo no macOS para evitar Errno 24 (Too many open files)
try:
    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    target_limit = min(4096, hard) if hard > 0 else 4096
    if soft < target_limit:
        resource.setrlimit(resource.RLIMIT_NOFILE, (target_limit, hard))
except Exception:
    pass

# Garante raiz do projeto no sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Carrega .env manualmente se necessário
env_file = BASE_DIR / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip("'\"")

# Configuração de Logging Executivo
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(BASE_DIR / "daily_sync.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("ICARO")

# Módulos PNCP
from pncp_intelligence.src.analytics import PNCPAnalytics
from pncp_intelligence.src.collector import PNCPCollector
from pncp_intelligence.src.db import PNCPDatabase
from pncp_intelligence.src.exporter import PNCPExporter
from pncp_intelligence.src.geo_map import GeoMapBuilder
from pncp_intelligence.src.observability import RunTracker, evaluate_health, persist_report
from pncp_intelligence.src.rematch import rematch_stale
from pncp_intelligence.src.telegram_bot import TelegramNotifier

# Módulos Scrapers & IA do I.C.A.R.O.
from core.pdf_extractor import extract_text_from_zip, extract_text_from_pdfs
from core.analyzer import analyze_opportunity
from core.storage_manager import cleanup_old_files


def load_candidate_profile() -> str:
    """Carrega o perfil executivo do candidato em Markdown para análise da IA."""
    paths = [
        BASE_DIR / "linkedin_carlos_artur_guimaraes_ago2026.md",
        BASE_DIR / "linkedin_profile.txt",
    ]
    for p in paths:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
    return ""


def get_all_scrapers():
    """Importa e mapeia os scrapers de oportunidades multilaterais, terceiro setor e privado."""
    try:
        from scrapers.scraper_pnud import get_new_opportunities as get_pnud
        from scrapers.scraper_unesco import get_new_opportunities as get_unesco
        from scrapers.scraper_oei import get_new_opportunities as get_oei
        from scrapers.scraper_undp_ptbr import get_new_opportunities as get_undp_ptbr
        from scrapers.scraper_unfpa import get_new_opportunities as get_unfpa
        from scrapers.scraper_unicef import get_new_opportunities as get_unicef
        from scrapers.scraper_iica import get_new_opportunities as get_iica
        from scrapers.scraper_terceiro_setor import get_new_opportunities as get_terceiro
        from scrapers.scraper_prosas import get_new_opportunities as get_prosas
        from scrapers.scraper_privado_edtechs import get_new_opportunities as get_edtechs
        from scrapers.scraper_privado_govtechs import get_new_opportunities as get_govtechs
        from scrapers.scraper_privado_consultorias import get_new_opportunities as get_consultorias
        from scrapers.scraper_senac import get_new_opportunities as get_senac
        from scrapers.scraper_sestsenat import get_new_opportunities as get_sestsenat
        from scrapers.scraper_firjan import get_new_opportunities as get_firjan

        return [
            # 1. Agências Multilaterais
            {"id": "unesco", "grupo": "agencias", "func": get_unesco, "db": "data/db/processados_unesco.json", "dir": "data/editais/unesco"},
            {"id": "pnud", "grupo": "agencias", "func": get_pnud, "db": "data/db/processados_pnud.json", "dir": "data/editais/pnud"},
            {"id": "oei", "grupo": "agencias", "func": get_oei, "db": "data/db/processados_oei.json", "dir": "data/editais/oei"},
            {"id": "undpptbr", "grupo": "agencias", "func": get_undp_ptbr, "db": "data/db/processados_undp_ptbr.json", "dir": "data/editais/undp_ptbr"},
            {"id": "unfpa", "grupo": "agencias", "func": get_unfpa, "db": "data/db/processados_unfpa.json", "dir": "data/editais/unfpa"},
            {"id": "unicef", "grupo": "agencias", "func": get_unicef, "db": "data/db/processados_unicef.json", "dir": "data/editais/unicef"},
            {"id": "iica", "grupo": "agencias", "func": get_iica, "db": "data/db/processados_iica.json", "dir": "data/editais/iica"},
            # 2. Terceiro Setor
            {"id": "terceiro_setor", "grupo": "terceiro_setor", "func": get_terceiro, "db": "data/db/processados_terceiro_setor.json", "dir": "data/editais/terceiro_setor"},
            {"id": "prosas", "grupo": "terceiro_setor", "func": get_prosas, "db": "data/db/processados_prosas.json", "dir": "data/editais/prosas"},
            # 3. Mercado Privado
            {"id": "privado_edtechs", "grupo": "privado", "func": get_edtechs, "db": "data/db/processados_privado_edtechs.json", "dir": "data/editais/privado_edtechs"},
            {"id": "privado_govtechs", "grupo": "privado", "func": get_govtechs, "db": "data/db/processados_privado_govtechs.json", "dir": "data/editais/privado_govtechs"},
            {"id": "privado_consultorias", "grupo": "privado", "func": get_consultorias, "db": "data/db/processados_privado_consultorias.json", "dir": "data/editais/privado_consultorias"},
            # 4. Sistema S & Instituições
            {"id": "senac", "grupo": "instituicoes", "func": get_senac, "db": "data/db/processados_senac.json", "dir": "data/editais/senac"},
            {"id": "sestsenat", "grupo": "instituicoes", "func": get_sestsenat, "db": "data/db/processados_sestsenat.json", "dir": "data/editais/sestsenat"},
            {"id": "firjan", "grupo": "instituicoes", "func": get_firjan, "db": "data/db/processados_firjan.json", "dir": "data/editais/firjan"},
        ]
    except Exception as e:
        logger.warning(f"Aviso ao carregar scrapers: {e}")
        return []


def run_scrapers_flow(target_group: Optional[str] = None) -> List[Dict[str, Any]]:
    """Executa a coleta e análise por IA das vagas e consultorias do I.C.A.R.O."""
    logger.info("🌐 [I.C.A.R.O.] Iniciando varredura de Agências, Terceiro Setor & Privado...")
    scrapers = get_all_scrapers()
    if target_group and target_group != "todos":
        scrapers = [s for s in scrapers if s["grupo"] == target_group or s["id"] == target_group]

    linkedin_text = load_candidate_profile()
    all_analyzed = []
    json_path = BASE_DIR / "pncp_intelligence" / "data" / "icaro" / "oportunidades_icaro.json"

    # Carrega existentes
    existing_opps = []
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                existing_opps = json.load(f)
        except Exception:
            existing_opps = []

    seen_keys = {f"{o.get('cargo')}_{o.get('url')}" for o in existing_opps}

    for src in scrapers:
        db_file = BASE_DIR / src["db"]
        dir_path = BASE_DIR / src["dir"]
        dir_path.mkdir(parents=True, exist_ok=True)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        processed_ids = set()
        if db_file.exists():
            try:
                with open(db_file, "r", encoding="utf-8") as f:
                    processed_ids = set(json.load(f))
            except Exception:
                pass

        try:
            opps = src["func"](str(dir_path), processed_ids)
            if not opps:
                continue

            logger.info(f"  [{src['id'].upper()}] {len(opps)} novas oportunidades encontradas. Analisando...")
            for opp in opps[:10]:  # Limite por fonte para proteger cota da API
                text = ""
                if "file_path" in opp:
                    text = extract_text_from_zip(opp["file_path"])
                else:
                    text = extract_text_from_pdfs(opp.get("file_paths", []))

                time.sleep(3)
                analysis = analyze_opportunity(text, linkedin_text)
                score = analysis.get("score", "Indefinido")

                if score in ["Alta", "Média"]:
                    opp_record = {
                        "id": f"icaro_{abs(hash(opp['title'] + opp.get('url', ''))) % 1000000:06d}",
                        "data_coleta": datetime.now().strftime("%Y-%m-%d"),
                        "grupo": src["grupo"],
                        "fonte_orgao": opp.get("source") or src["id"].upper(),
                        "titulo": opp["title"],
                        "cargo": analysis.get("cargo", opp["title"]),
                        "objeto": analysis.get("objeto", "Não informado"),
                        "local": analysis.get("local", "Remoto / Híbrido"),
                        "contrato": analysis.get("contrato", "Consultoria por Produto"),
                        "valor": analysis.get("valor", "Não informado"),
                        "prazo": analysis.get("prazo", opp.get("end_date", "Ver Edital")),
                        "score": score,
                        "reasoning": analysis.get("reasoning", ""),
                        "url": opp.get("url", ""),
                    }

                    k = f"{opp_record['cargo']}_{opp_record['url']}"
                    if k not in seen_keys:
                        seen_keys.add(k)
                        all_analyzed.append(opp_record)
                        existing_opps.insert(0, opp_record)

                if score != "Erro":
                    processed_ids.add(opp["id"])

            with open(db_file, "w", encoding="utf-8") as f:
                json.dump(list(processed_ids), f)

        except Exception as e:
            logger.error(f"  Erro no scraper {src['id']}: {e}")

    # Salva base consolidada do I.C.A.R.O.
    if all_analyzed:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(existing_opps, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ [I.C.A.R.O.] {len(all_analyzed)} novas oportunidades de alta/média relevância salvas.")

    return existing_opps


def run_pncp_flow(db: PNCPDatabase, collector: PNCPCollector, tracker: RunTracker):
    """Executa a coleta, reclassificação e scoring do motor de Compras Públicas (PNCP)."""
    logger.info("🏛️ [PNCP] 1. Executando varredura indexada e oportunidades abertas no PNCP...")
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
        logger.info(f"✅ [PNCP] {len(novos)} editais com propostas abertas mapeados com sucesso.")
    except Exception as e:
        run_error = f"{type(e).__name__}: {e}"
        logger.error(f"⚠️ [PNCP] Erro ao consultar API ao vivo: {e}")

    # Rematch e Observabilidade
    try:
        rm = rematch_stale(db, collector.matcher)
        if rm.get("reprocessed", 0) > 0:
            logger.info(f"🔁 [PNCP] Rematch: {rm['reprocessed']} editais reprocessados.")
    except Exception as e:
        logger.error(f"⚠️ [PNCP] Erro no rematch: {e}")

    tracker.finish(
        audits=collector.audits,
        rows_scanned=sum(a.records for a in collector.audits.values()),
        rows_matched=len(novos),
        api_errors=collector.api_errors,
        failed_chunks=collector.failed_chunks,
        error=run_error,
    )

    report = evaluate_health(str(db.db_path))
    persist_report(str(db.db_path), report, collector.run_id)
    logger.info(f"🩺 [PNCP] Saúde dos dados: {report.overall} {report.counts()}")
    return report


def main():
    parser = argparse.ArgumentParser(description="I.C.A.R.O. — Inteligência de Captura e Análise de Oportunidades")
    parser.add_argument(
        "--mode",
        choices=["all", "pncp", "scrapers", "dashboard", "export"],
        default="all",
        help="Modo de execução: all (completo integrado), pncp (licitações), scrapers (agências/privado), dashboard (Streamlit), export (planilhas/mapas)"
    )
    parser.add_argument("--group", type=str, default="todos", help="Grupo para os scrapers: agencias, terceiro_setor, privado, instituicoes, todos")
    parser.add_argument("--port", type=int, default=8501, help="Porta do Streamlit (padrão: 8501)")
    parser.add_argument("--no-telegram", action="store_true", help="Desativa envio de mensagens para o Telegram")

    args = parser.parse_args()

    logger.info("==================================================================")
    logger.info("🚀 I.C.A.R.O. INTELLIGENCE SUITE • INICIALIZANDO")
    logger.info(f"🕒 Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Modo: {args.mode.upper()}")
    logger.info("==================================================================")

    if args.mode == "dashboard":
        app_path = BASE_DIR / "pncp_intelligence" / "dashboard" / "app.py"
        logger.info(f"🖥️ Abrindo Dashboard I.C.A.R.O. na porta {args.port}...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path), "--server.port", str(args.port)])
        return 0

    db = PNCPDatabase()
    analytics = PNCPAnalytics(db)
    collector = PNCPCollector(db=db)
    exporter = PNCPExporter(analytics)
    telegram = TelegramNotifier()

    # 1. Executa Scrapers do I.C.A.R.O. (se mode == all ou scrapers)
    icaro_opps = []
    if args.mode in ["all", "scrapers"]:
        icaro_opps = run_scrapers_flow(target_group=args.group)

    # 2. Executa Motor PNCP (se mode == all ou pncp)
    report_health = None
    if args.mode in ["all", "pncp"]:
        tracker = RunTracker(db, trigger=os.getenv("GITHUB_EVENT_NAME", "manual"))
        collector.run_id = tracker.start(keywords_hash=collector.matcher.fingerprint())
        report_health = run_pncp_flow(db, collector, tracker)

    # 3. Calcula Radar e Reexporta Artefatos (Excel, Parquet, Mapa)
    logger.info("📊 Calculando Radar de Candidatura e Exportando Planilhas...")
    df_geral = analytics.get_dataframe()
    df_geral = df_geral[df_geral["matched_category"].notna() & (df_geral["matched_category"] != "")]
    df_radar = analytics.live_candidacy_radar(df_geral)

    try:
        paths = exporter.export_all()
        logger.info(f"✅ Excel atualizado: {paths['excel']}")
    except Exception as e:
        logger.error(f"⚠️ Erro ao exportar Excel: {e}")

    try:
        GeoMapBuilder.exportar_mapa_html(df_geral, "pncp_intelligence/data/processed/mapa_interativo_oportunidades_pncp.html")
        GeoMapBuilder.exportar_mapa_html(df_geral, "docs/index.html")
        logger.info("✅ Mapa Interativo Esri atualizado com sucesso!")
    except Exception as e:
        logger.error(f"⚠️ Erro ao reexportar mapa: {e}")

    # 4. Disparo do Briefing Unificado no Telegram
    if not args.no_telegram and telegram.is_configured:
        if not icaro_opps:
            json_icaro = BASE_DIR / "pncp_intelligence" / "data" / "icaro" / "oportunidades_icaro.json"
            if json_icaro.exists():
                try:
                    with open(json_icaro, "r", encoding="utf-8") as f:
                        icaro_opps = json.load(f)
                except Exception:
                    pass

        logger.info("📱 Disparando Briefing Executivo Consolidado no Telegram (PNCP + I.C.A.R.O.)...")
        if report_health and report_health.overall == "FAIL":
            logger.error("⛔ Saúde dos dados em FAIL: envio suprimido para proteger qualidade analítica.")
        else:
            sucesso = telegram.send_integrated_briefing(df_radar, icaro_opps, top_pncp=6, top_icaro=6)
            if sucesso:
                logger.info("🎉 Briefing Integrado enviado com sucesso para o seu Telegram!")
            else:
                logger.warning("⚠️ Falha ao entregar mensagem no Telegram.")
    elif not telegram.is_configured:
        logger.info("ℹ️ Telegram não configurado no .env (TELEGRAM_TOKEN / TELEGRAM_CHAT_ID).")

    logger.info("==================================================================")
    logger.info("🎉 ROTINA EXECUTADA COM SUCESSO PELO I.C.A.R.O.!")
    logger.info("==================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
