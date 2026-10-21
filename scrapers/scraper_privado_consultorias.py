"""
I.C.A.R.O. — Scraper Privado Consultorias (Gestão Pública e Estratégia via Gupy)
==================================================================================
Wrapper que carrega os subdomínios do grupo 'privado_consultorias' do arquivo
config/gupy_sources.yaml e delega ao motor genérico scraper_gupy_base.
"""

import os
import yaml
from scrapers.scraper_gupy_base import get_gupy_opportunities


def _load_config():
    """Carrega configuração YAML do diretório config/."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        "gupy_sources.yaml",
    )
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_new_opportunities(download_dir, processed_ids):
    """
    Contrato padrão I.C.A.R.O.
    Retorna lista de oportunidades de consultorias de gestão pública e estratégia.
    """
    config = _load_config()

    subdomains = config.get("privado_consultorias", [])
    keywords = config.get("keywords", [])
    negative_keywords = config.get("negative_keywords", [])

    print(f"[Privado - Consultorias] Monitorando {len(subdomains)} consultorias via Gupy...")

    return get_gupy_opportunities(
        subdomains=subdomains,
        keywords=keywords,
        negative_keywords=negative_keywords,
        download_dir=download_dir,
        processed_ids=processed_ids,
        source_label="Consultoria",
    )
