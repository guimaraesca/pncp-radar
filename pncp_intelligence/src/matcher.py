"""Motor de casamento textual e classificação temática para o PNCP Intelligence.

Normaliza textos (remoção de acentos, case-insensitive) e mapeia cada edital
para categorias e subtemas configurados no YAML de palavras-chave.
"""

import hashlib
import json
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

    def fingerprint(self) -> str:
        """Hash (12 hex) do dicionário vigente: termos e exclusões normalizados.

        Não muda com comentários ou ordem no YAML; muda quando qualquer termo
        ou exclusão muda. Usado na linhagem para saber com qual versão do
        dicionário cada edital foi classificado.
        """
        canon = {
            "categories": {
                ck: {
                    sk: sorted(normalize_text(t) for t in (sv.get("terms") or []))
                    for sk, sv in (cv.get("subtemas") or {}).items()
                }
                for ck, cv in self.categories.items()
            },
            "exclusions": sorted(self.exclusions),
        }
        blob = json.dumps(canon, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:12]

    def add_custom_term(self, term: str, category: str = "termos_personalizados", subtema: str = "custom") -> None:
        """Permite adicionar termos dinamicamente em tempo de execução."""
        if category not in self.categories:
            self.categories[category] = {"name": category, "subtemas": {}}
        if subtema not in self.categories[category]["subtemas"]:
            self.categories[category]["subtemas"][subtema] = {"name": subtema, "terms": []}

        self.categories[category]["subtemas"][subtema]["terms"].append(term)

    def get_search_queries(self) -> List[str]:
        """Retorna a lista de termos-chave estratégicos e qualificados para consulta ativa na API /api/search/ do PNCP."""
        priority_queries = [
            # 1. Educação Digital, Pensamento Computacional & STEAM
            "pensamento computacional",
            "letramento computacional",
            "robotica educacional",
            "robotica pedagogica",
            "bncc computacao",
            "cultura maker",
            "laboratorio maker",
            "espaco maker",
            "plataforma gamificada",
            "professor orientador de ti",
            # 2. Inovação & Tecnologias Educacionais
            "solucao educacional",
            "solucoes educacionais",
            "solucao educacional integrada",
            "solucao pedagogica",
            "solucoes pedagogicas",
            "plataforma educacional",
            "plataforma de aprendizagem",
            "ambiente virtual de aprendizagem",
            "recursos tecnologicos pedagogicos",
            "learning analytics",
            # 3. Avaliação Educacional, IDEB & VAAR
            "vaar",
            "complementacao vaar",
            "condicionalidades vaar",
            "ideb",
            "saeb",
            "recomposicao de aprendizagem",
            "avaliacao diagnostica",
            "avaliacao formativa",
            "avaliacao educacional",
            "fluencia leitora",
            # 4. Políticas Educacionais & Gestão
            "politicas educacionais",
            "gestao educacional",
            "gestao escolar",
            "assessoria pedagogica",
            "consultoria educacional",
            "consultoria pedagogica",
            "formacao continuada de professores",
            "busca ativa escolar",
            # 5. Dados, IA, BI & Monitoramento de Políticas Públicas
            "inteligencia artificial",
            "machine learning",
            "ia generativa",
            "business intelligence",
            "power bi",
            "painel de indicadores",
            "ciencia de dados",
            "analise de dados",
            "engenharia de dados",
            "data warehouse",
            "data lake",
            "big data",
            "monitoramento e avaliacao",
            "avaliacao de impacto",
            "avaliacao de politicas publicas",
            "sala de situacao",
            "observatorio de dados",
            "geoprocessamento",
            # 6. Governança, LGPD, PMO & Transformação Digital
            "governanca de dados",
            "governanca de ti",
            "lgpd",
            "protecao de dados",
            "transformacao digital",
            "governo digital",
            "cidades inteligentes",
            "escritorio de projetos",
            "mapeamento de processos",
            "gestao por processos",
            "bpmn",
            "plano diretor de ti",
            "pdti",
            "planejamento estrategico institucional",
            "consultoria em gestao publica",
            "consultoria em politicas publicas",
            "consultoria em dados",
            "consultoria em ti",
            "consultoria em transformacao digital",
            "assessoria em gestao publica",
            "assessoria em politicas publicas",
            "assessoria em ti",
            "assessoria em dados",
        ]
        return priority_queries

    def match(
        self,
        objeto: Optional[str],
        informacao_complementar: Optional[str] = "",
        search_hint: Optional[str] = None,
    ) -> Tuple[bool, str, str, List[str]]:
        """Avalia se o edital corresponde a algum tema de interesse.
        
        Retorna:
            (is_match, categoria_nome, subtema_nome, termos_encontrados)
        """
        full_text = f"{objeto or ''} {informacao_complementar or ''}"
        norm_text = normalize_text(full_text)

        if not norm_text and not search_hint:
            return False, "", "", []

        # 1. Checagem imediata de exclusões cirúrgicas (Blacklist anti-ruído)
        for excl in self.exclusions:
            if excl and excl in norm_text:
                return False, "", "", []

        # 2. Busca termos em cada categoria e subtema no texto do edital
        matches_found: List[str] = []
        sub_scores: Dict[Tuple[str, str], int] = {}
        anchor_terms = {
            "pensamento computacional", "letramento computacional", "pensamento e do letramento computacional",
            "robotica educacional", "robotica pedagogica", "bncc computacao", "cultura maker", "laboratorio maker",
            "vaar", "condicionalidades vaar", "ideb", "saeb", "recomposicao de aprendizagem",
            "inteligencia artificial", "machine learning", "ia generativa", "business intelligence",
            "power bi", "engenharia de dados", "ciencia de dados", "monitoramento e avaliacao",
            "lgpd", "protecao de dados", "transformacao digital", "governo digital",
            "escritorio de projetos", "governanca de dados", "governanca de ti", "pdti",
            "solucao educacional", "solucoes educacionais", "solucao pedagogica", "solucoes pedagogicas",
        }

        def _scan_text(target_norm_text: str) -> None:
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

                        pattern = r"\b" + re.escape(norm_term) + r"\b"
                        if re.search(pattern, target_norm_text):
                            if raw_term not in matches_found:
                                matches_found.append(raw_term)
                            pts = 500 if norm_term in anchor_terms else (120 if len(norm_term.split()) >= 2 else 40)
                            sub_scores[(cat_name, sub_name)] = sub_scores.get((cat_name, sub_name), 0) + pts

        if norm_text:
            _scan_text(norm_text)

        # 3. Se veio da busca indexada do PNCP (/api/search/?q=...) e o termo estava nos itens/anexos
        if search_hint:
            hint_norm = normalize_text(search_hint)
            if not matches_found:
                if hint_norm in anchor_terms or (len(hint_norm.split()) >= 2 and len(hint_norm) >= 10):
                    _scan_text(hint_norm)
            elif hint_norm in anchor_terms and hint_norm not in [normalize_text(m) for m in matches_found]:
                _scan_text(hint_norm)

        if matches_found and sub_scores:
            best_cat_name, best_sub_name = max(sub_scores.items(), key=lambda kv: kv[1])[0]
            return True, best_cat_name, best_sub_name, matches_found

        return False, "", "", []
