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

# Garante raiz do projeto no sys.path e diretório de trabalho correto
BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)
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


def get_all_scrapers(registry: Optional[Any] = None):
    """Carrega scrapers especializados e integra dinamicamente todas as fontes cadastradas no catálogo."""
    from core.source_registry import SourceRegistry
    from scrapers.universal_crawler import crawl_source_opportunities

    if registry is None:
        registry = SourceRegistry()

    specialized_funcs = {}
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

        specialized_funcs = {
            "unesco": get_unesco,
            "pnud": get_pnud,
            "oei": get_oei,
            "undp_cj": get_undp_ptbr,
            "unfpa_br": get_unfpa,
            "unicef_br": get_unicef,
            "iica": get_iica,
            "terceiro_setor": get_terceiro,
            "prosas": get_prosas,
            "privado_edtechs": get_edtechs,
            "privado_govtechs": get_govtechs,
            "privado_consultorias": get_consultorias,
            "senac": get_senac,
            "sestsenat": get_sestsenat,
            "firjan": get_firjan,
        }
    except Exception as e:
        logger.warning(f"Aviso ao carregar scrapers legados: {e}")

    scrapers = []
    for s in registry.get_sources(only_active=True):
        sid = s["id"]
        grupo = s.get("grupo", "agencias")

        if sid in specialized_funcs:
            fn = specialized_funcs[sid]
        else:
            # Crawler universal inteligente para qualquer portal/URL da lista
            fn = lambda d_dir, p_ids, s_info=s: crawl_source_opportunities(s_info, d_dir, p_ids)

        scrapers.append({
            "id": sid,
            "nome": s.get("nome", sid.upper()),
            "grupo": grupo,
            "func": fn,
            "db": f"data/db/processados_{sid}.json",
            "dir": f"data/editais/{sid}",
        })

    return scrapers


def run_scrapers_flow(
    target_group: Optional[str] = None,
    target_source: Optional[str] = None,
    registry: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """Executa a coleta e análise por IA das vagas e consultorias do I.C.A.R.O. sobre todas as fontes cadastradas."""
    logger.info("🌐 [I.C.A.R.O.] Iniciando varredura dinâmica de Agências, Governo & Mercado...")
    scrapers = get_all_scrapers(registry=registry)

    if target_source:
        scrapers = [s for s in scrapers if s["id"] == target_source]
    elif target_group and target_group != "todos":
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

            logger.info(f"  [{src['nome']}] {len(opps)} novas oportunidades encontradas. Analisando...")
            for opp in opps[:8]:  # Limite por fonte para proteger cota da API
                text = ""
                if "file_path" in opp:
                    text = extract_text_from_zip(opp["file_path"])
                else:
                    text = extract_text_from_pdfs(opp.get("file_paths", []))

                time.sleep(2)
                analysis = analyze_opportunity(text, linkedin_text)
                score = analysis.get("score", "Indefinido")

                if score in ["Alta", "Média"]:
                    prazo_val = analysis.get("prazo")
                    if not prazo_val or str(prazo_val).strip() in ["Não informado", "Ver Edital", ""]:
                        prazo_val = opp.get("end_date") or "Ver Edital"

                    opp_record = {
                        "id": f"icaro_{abs(hash(opp['title'] + opp.get('url', ''))) % 1000000:06d}",
                        "data_coleta": datetime.now().strftime("%Y-%m-%d"),
                        "grupo": src["grupo"],
                        "fonte_orgao": opp.get("source") or src["nome"],
                        "titulo": opp["title"],
                        "cargo": analysis.get("cargo", opp["title"]),
                        "objeto": analysis.get("objeto", "Não informado"),
                        "pre_requisitos": analysis.get("pre_requisitos") or analysis.get("requisitos") or "Graduação e pós-graduação compatíveis, com experiência prévia na área.",
                        "aderencia": analysis.get("aderencia") or analysis.get("reasoning", ""),
                        "local": analysis.get("local", "Remoto / Híbrido"),
                        "contrato": analysis.get("contrato", "Consultoria por Produto"),
                        "valor": analysis.get("valor", "Não informado"),
                        "prazo": prazo_val,
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
    parser.add_argument("--group", type=str, default="todos", help="Grupo para os scrapers: agencias, governo, terceiro_setor, privado, instituicoes, todos")
    parser.add_argument("--source", type=str, default=None, help="Executa exclusivamente uma fonte específica (ex: --source mec, --source oei, --source acnur)")
    parser.add_argument("--sources-file", type=str, default=None, help="Caminho para arquivo de fontes alternativo (YAML ou TXT)")
    parser.add_argument("--add-source", type=str, default=None, help="Adiciona uma nova fonte ao catálogo no formato: 'Nome|URL|grupo'")
    parser.add_argument("--import-sources", type=str, default=None, help="Importa uma lista de URLs de um arquivo texto (uma por linha)")
    parser.add_argument("--list-sources", action="store_true", help="Lista todas as fontes cadastradas no catálogo e encerra")
    parser.add_argument("--port", type=int, default=8501, help="Porta do Streamlit (padrão: 8501)")
    parser.add_argument("--no-telegram", action="store_true", help="Desativa envio de mensagens para o Telegram")
    parser.add_argument("--cooldown-days", type=int, default=14, help="Dias de cooldown para não renotificar o mesmo edital no Telegram (padrão: 14)")
    parser.add_argument("--force-resend", action="store_true", help="Força reenvio mesmo para editais já notificados no período de cooldown")

    args = parser.parse_args()

    # Inicializa Registro Dinâmico de Fontes
    from core.source_registry import SourceRegistry
    sources_path = Path(args.sources_file) if args.sources_file else None
    registry = SourceRegistry(sources_file=sources_path)

    # Ações rápidas de gestão de fontes
    if args.add_source:
        parts = args.add_source.split("|")
        nome = parts[0].strip() if len(parts) > 1 else None
        url = parts[1].strip() if len(parts) > 1 else parts[0].strip()
        grupo = parts[2].strip() if len(parts) > 2 else "agencias"
        nova = registry.add_source(url=url, nome=nome, grupo=grupo)
        print(f"✅ Fonte cadastrada com sucesso no catálogo:\n   ID: {nova['id']}\n   Nome: {nova['nome']}\n   URL: {nova['url']}\n   Grupo: {nova['grupo']}")
        return 0

    if args.import_sources:
        imp_path = Path(args.import_sources)
        if imp_path.exists():
            with open(imp_path, "r", encoding="utf-8") as f:
                content = f.read()
            qtd = registry.load_from_text_list(content)
            registry.save()
            print(f"✅ {qtd} fontes importadas com sucesso de {imp_path} para config/sources.yaml!")
            return 0
        else:
            print(f"❌ Arquivo não encontrado: {imp_path}")
            return 1

    if args.list_sources:
        fontes = registry.get_sources(only_active=False)
        print("==================================================================")
        print(f"📋 I.C.A.R.O. • DIRETÓRIO DE FONTES CADASTRADAS ({len(fontes)} portais)")
        print("==================================================================")
        for i, s in enumerate(fontes, 1):
            status = "🟢 Ativa" if s.get("ativo", True) else "⚪ Inativa"
            print(f"[{i:02d}] {status} | ID: {s['id']:<16} | Grupo: {s.get('grupo','-'):<15} | {s.get('nome')}\n     🔗 {s.get('url')}")
        print("==================================================================")
        return 0

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
        icaro_opps = run_scrapers_flow(target_group=args.group, target_source=args.source, registry=registry)

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
            logger.warning("⚠️ Observabilidade com apontamento de qualidade nos dados do PNCP, mas prosseguindo com envio do briefing.")

        sucesso = telegram.send_integrated_briefing(
            df_radar=df_radar,
            icaro_opps=icaro_opps,
            top_pncp=6,
            top_icaro=6,
            db=db,
            cooldown_days=args.cooldown_days,
            filter_notified=not args.force_resend,
        )
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
