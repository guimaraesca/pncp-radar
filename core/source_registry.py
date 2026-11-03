"""Gerenciamento Dinâmico de Fontes e Portais do I.C.A.R.O.

Permite carregar, listar, filtrar e adicionar novos portais de oportunidades
diretamente via arquivo de configuração YAML/JSON ou lista de URLs.
"""

import os
import re
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger("SourceRegistry")

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES_PATH = BASE_DIR / "config" / "sources.yaml"


def normalize_source_id(url: str, nome: Optional[str] = None) -> str:
    """Gera um identificador amigável a partir da URL ou nome."""
    if nome:
        clean = re.sub(r"[^\w\s-]", "", nome).strip().lower()
        return re.sub(r"[-\s]+", "_", clean)[:30]
    domain = urlparse(url).netloc.replace("www.", "")
    parts = domain.split(".")
    base = parts[0] if parts[0] not in ["gov", "org", "com"] else (parts[1] if len(parts) > 1 else parts[0])
    return re.sub(r"[^\w]", "_", base).lower()[:30]


class SourceRegistry:
    """Catálogo central e dinâmico de portais de recrutamento e editais."""

    def __init__(self, sources_file: Optional[Path] = None):
        self.sources_file = Path(sources_file) if sources_file else DEFAULT_SOURCES_PATH
        self._sources: List[Dict[str, Any]] = []
        self.reload()

    def reload(self) -> None:
        """Recarrega a lista de fontes do arquivo configurado."""
        if not self.sources_file.exists():
            logger.warning(f"Arquivo de fontes não encontrado: {self.sources_file}. Iniciando vazio.")
            self._sources = []
            return

        try:
            with open(self.sources_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            if isinstance(data, dict) and "fontes" in data:
                self._sources = data["fontes"]
            elif isinstance(data, list):
                self._sources = data
            else:
                self._sources = []

            logger.info(f"📋 {len(self._sources)} fontes de oportunidades carregadas de {self.sources_file.name}.")
        except Exception as e:
            logger.error(f"Erro ao carregar fontes de {self.sources_file}: {e}")
            self._sources = []

    def get_sources(
        self,
        group: Optional[str] = None,
        source_id: Optional[str] = None,
        only_active: bool = True
    ) -> List[Dict[str, Any]]:
        """Retorna fontes filtradas por grupo, id ou status de ativação."""
        res = []
        for s in self._sources:
            if only_active and not s.get("ativo", True):
                continue
            if group and group != "todos" and s.get("grupo") != group and s.get("id") != group:
                continue
            if source_id and s.get("id") != source_id:
                continue
            res.append(s)
        return res

    def add_source(
        self,
        url: str,
        nome: Optional[str] = None,
        grupo: str = "agencias",
        tipo: str = "generic_crawler"
    ) -> Dict[str, Any]:
        """Adiciona uma nova fonte ao arquivo sources.yaml."""
        source_id = normalize_source_id(url, nome)

        # Checa duplicidade de id ou url
        for s in self._sources:
            if s.get("id") == source_id or s.get("url") == url:
                logger.info(f"Fonte {source_id} ({url}) já cadastrada no catálogo.")
                return s

        nome_final = nome or urlparse(url).netloc
        nova_fonte = {
            "id": source_id,
            "nome": nome_final,
            "url": url,
            "grupo": grupo,
            "tipo": tipo,
            "ativo": True,
        }

        self._sources.append(nova_fonte)
        self.save()
        logger.info(f"✨ Nova fonte adicionada com sucesso: {nome_final} ({url})")
        return nova_fonte

    def load_from_text_list(self, text_or_file_content: str, default_group: str = "agencias") -> int:
        """Importa fontes a partir de uma lista de URLs em texto (uma por linha ou 'Nome (LINK)')."""
        added = 0
        lines = text_or_file_content.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Suporte ao formato: Nome (https://...) ou Nome ([LINK](https://...))
            url_match = re.search(r"https?://[^\s\)\>]+", line)
            if not url_match:
                continue
            url = url_match.group(0).rstrip(".,;")

            # Extrai nome se houver
            nome = None
            nome_match = re.match(r"^([^\(\[\:\-]+)[\(\[\:\-]", line)
            if nome_match:
                nome = nome_match.group(1).strip()

            self.add_source(url=url, nome=nome, grupo=default_group)
            added += 1

        return added

    def save(self) -> None:
        """Persiste as fontes atualizadas no arquivo sources.yaml."""
        self.sources_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.sources_file, "w", encoding="utf-8") as f:
            yaml.dump({"fontes": self._sources}, f, allow_unicode=True, sort_keys=False, indent=2)
