#!/usr/bin/env python3
"""CLI e Orquestrador do Pipeline de Inteligência PNCP.

Permite executar coletas históricas, monitorar propostas ativas,
gerar exportações para Excel e inicializar o dashboard interativo.
"""

import argparse
import logging
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Adiciona o diretório atual ao sys.path para importações locais
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pncp_intelligence.src.analytics import PNCPAnalytics
from pncp_intelligence.src.collector import PNCPCollector
from pncp_intelligence.src.db import PNCPDatabase
from pncp_intelligence.src.exporter import PNCPExporter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Pipeline")


def main():
    parser = argparse.ArgumentParser(description="PNCP Market Intelligence & Edital Analytics")
    parser.add_argument(
        "--mode",
        choices=["live", "collect", "export", "dashboard", "stats"],
        default="stats",
        help="Modo de execução: live (propostas abertas), collect (histórico), export (Excel/Parquet), dashboard (Streamlit), stats (resumo)",
    )
    parser.add_argument("--days", type=int, default=None, help="Quantidade de dias passados para coleta histórica")
    parser.add_argument("--years", type=float, default=2.0, help="Quantidade de anos passados para coleta histórica (padrão: 2)")
    parser.add_argument("--modalidades", nargs="+", type=int, default=[6, 4, 8, 12], help="IDs de modalidades (padrão: 6 4 8 12)")
    parser.add_argument("--port", type=int, default=8501, help="Porta para o Streamlit Dashboard")
    parser.add_argument("--download-pdfs", action="store_true", help="Baixa arquivos PDF oficiais dos editais e TRs localmente")

    args = parser.parse_args()

    db = PNCPDatabase()
    analytics = PNCPAnalytics(db)
    exporter = PNCPExporter(analytics)
    collector = PNCPCollector(db=db, download_pdfs=args.download_pdfs)

    if args.mode == "stats":
        stats = db.get_stats()
        print("\n" + "=" * 50)
        print("📊 STATUS DA BASE PNCP INTELLIGENCE")
        print("=" * 50)
        print(f"Total de Editais Mapeados: {stats['total_editais']:,}")
        print(f"Total de Itens Detalhados: {stats['total_itens']:,}")
        print(f"Volume Financeiro Estimado: R$ {stats['valor_total_estimado']:,.2f}")
        print(f"Checkpoints Concluídos:   {stats['total_checkpoints']}")
        print("\nCategorias:")
        for cat in stats["categorias"]:
            print(f"  - {cat['matched_category'] or 'Sem categoria'}: {cat['count']} editais")
        print("=" * 50 + "\n")

    elif args.mode == "live":
        print("\n🎯 Buscando propostas abertas no PNCP para os temas de interesse...")
        opps = collector.collect_live_opportunities(days_ahead=30, modalidades=args.modalidades)
        print(f"\n✅ Concluído! {len(opps)} editais relevantes identificados e priorizados por logística.")
        paths = exporter.export_all()
        print(f"📁 Planilhas atualizadas em: {paths['excel']}\n")

    elif args.mode == "collect":
        today = date.today()
        if args.days:
            start_date = today - timedelta(days=args.days)
        else:
            start_date = today - timedelta(days=int(args.years * 365))

        print(f"\n🚀 Iniciando coleta histórica de {start_date} até {today} ({args.years} anos)...")
        res = collector.collect_period(start_date=start_date, end_date=today, modalidades=args.modalidades)
        print(f"\n✅ Coleta concluída! {res['total_scanned']} analisados | {res['total_matches']} matches salvos | {res['total_items_saved']} itens salvos.")
        paths = exporter.export_all()
        print(f"📁 Relatório consolidado gerado: {paths['excel']}\n")

    elif args.mode == "export":
        print("\n📊 Gerando relatórios analíticos em Excel multi-abas, Parquet e CSV...")
        paths = exporter.export_all()
        print(f"✅ Excel gerado:   {paths['excel']}")
        print(f"✅ Parquet Editais: {paths['parquet_editais']}")
        print(f"✅ Parquet Itens:   {paths['parquet_itens']}")
        print(f"✅ CSV Editais:     {paths['csv']}\n")

    elif args.mode == "dashboard":
        print(f"\n🌐 Inicializando Dashboard Streamlit na porta {args.port}...")
        subprocess.run([
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "pncp_intelligence/dashboard/app.py",
            "--server.port",
            str(args.port),
            "--server.headless",
            "true",
        ])


if __name__ == "__main__":
    main()
