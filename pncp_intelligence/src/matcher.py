"""Motor de casamento textual e classificação temática para o PNCP Intelligence.

Normaliza textos (remoção de acentos, case-insensitive) e mapeia cada edital
para categorias e subtemas configurados no YAML de palavras-chave.
"""

import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml


def normalize_text(text: Optional[str]) -> str:
    """Remove acentos, pontuações excessivas e converte para minúsculas."""
    if not text:
        return ""
    # Decompõe caracteres acentuados
    nfkd = unicodedata.normalize("NFKD", text)
    # Remove marcas de diacríticos
    without_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Minúsculas e normalização de espaços
    cleaned = re.sub(r"\s+", " ", without_accents.lower()).strip()
    return cleaned


class ThematicMatcher:
    def __init__(self, config_path: str = "pncp_intelligence/config/keywords.yaml"):
        self.config_path = Path(config_path)
        self.categories: Dict[str, Any] = {}
        self.exclusions: List[str] = []
        self._load_config()

    def _load_config(self) -> None:
        if not self.config_path.exists():
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        self.categories = data.get("categories", {})
        raw_exclusions = data.get("exclusions", [])
        self.exclusions = [normalize_text(e) for e in raw_exclusions if e]

    def add_custom_term(self, term: str, category: str = "termos_personalizados", subtema: str = "custom") -> None:
        """Permite adicionar termos dinamicamente em tempo de execução."""
        if category not in self.categories:
            self.categories[category] = {"name": category, "subtemas": {}}
        if subtema not in self.categories[category]["subtemas"]:
            self.categories[category]["subtemas"][subtema] = {"name": subtema, "terms": []}

        self.categories[category]["subtemas"][subtema]["terms"].append(term)

    def match(self, objeto: Optional[str], informacao_complementar: Optional[str] = "") -> Tuple[bool, str, str, List[str]]:
        """Avalia se o edital corresponde a algum tema de interesse.
        
        Retorna:
            (is_match, categoria_nome, subtema_nome, termos_encontrados)
        """
        full_text = f"{objeto or ''} {informacao_complementar or ''}"
        norm_text = normalize_text(full_text)

        if not norm_text:
            return False, "", "", []

        # 1. Verifica exclusões imediatas
        for excl in self.exclusions:
            if excl and excl in norm_text:
                return False, "", "", []

        # 2. Busca termos em cada categoria e subtema
        matches_found: List[str] = []
        matched_cat_name = ""
        matched_sub_name = ""

        for cat_key, cat_data in self.categories.items():
            cat_name = cat_data.get("name", cat_key)
            subtemas = cat_data.get("subtemas", {})

            for sub_key, sub_data in subtemas.items():
                sub_name = sub_data.get("name", sub_key)
                terms = sub_data.get("terms", []) or []

                for raw_term in terms:
                    norm_term = normalize_text(raw_term)
                    if not norm_term:
                        continue

                    # Casamento exato de substring com limite de palavra se termo for curto
                    pattern = r"\b" + re.escape(norm_term) + r"\b"
                    if re.search(pattern, norm_text):
                        matches_found.append(raw_term)
                        if not matched_cat_name:
                            matched_cat_name = cat_name
                            matched_sub_name = sub_name

        if matches_found:
            return True, matched_cat_name, matched_sub_name, matches_found

        return False, "", "", []
