"""
I.C.A.R.O. — Scraper Terceiro Setor (Fundações e Institutos via Gupy)
======================================================================
Wrapper que carrega os subdomínios do grupo 'terceiro_setor' do arquivo
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
    Retorna lista de oportunidades de fundações e institutos do Terceiro Setor.
    """
    config = _load_config()

    subdomains = config.get("terceiro_setor", [])
    keywords = config.get("keywords", [])
    negative_keywords = config.get("negative_keywords", [])

    print(f"[Terceiro Setor] Monitorando {len(subdomains)} fundações/institutos via Gupy...")

    return get_gupy_opportunities(
        subdomains=subdomains,
        keywords=keywords,
        negative_keywords=negative_keywords,
        download_dir=download_dir,
        processed_ids=processed_ids,
        source_label="Terceiro Setor",
    )
