"""Observabilidade de dados do pipeline PNCP: os 5 pilares.

    Freshness     a base foi atualizada quando? (execuções + data da fonte)
    Volume        perdeu linhas/UFs/períodos? a API falhou e virou "vazio"?
    Distribution  valores, datas e domínios dentro do esperado? termos enviesados?
    Schema        a API mudou nomes/tipos de campos? o banco perdeu colunas?
    Lineage       de qual execução, endpoint e versão do dicionário veio cada linha?

Uso:
    # Como biblioteca (dashboard / pipeline)
    report = evaluate_health(db_path="pncp_intelligence/data/pncp_intelligence.sqlite")

    # Como gate de CI (exit 1 se algum check estiver FAIL)
    python -m pncp_intelligence.src.observability --persist --gate --markdown

Convenção de status: PASS < SKIP < WARN < FAIL. SKIP = sem baseline para comparar
(nunca é mascarado como PASS). Limites em pncp_intelligence/config/observability.yaml.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml

DEFAULT_DB_PATH = "pncp_intelligence/data/pncp_intelligence.sqlite"
DEFAULT_CONFIG_PATH = "pncp_intelligence/config/observability.yaml"
DEFAULT_KEYWORDS_PATH = "pncp_intelligence/config/keywords.yaml"

PILLARS = ["Freshness", "Volume", "Distribution", "Schema", "Lineage"]
_SEVERITY = {"PASS": 0, "SKIP": 1, "WARN": 2, "FAIL": 3}

# Valores de linhagem usados no backfill de linhas anteriores ao rastreio.
LEGACY_RUN_ID = "legacy-backfill"
LEGACY_ENDPOINT = "legacy"

# ---------------------------------------------------------------------------
# Limites padrão (sobrescritos por observability.yaml)
# ---------------------------------------------------------------------------
DEFAULT_CONFIG: Dict[str, Any] = {
    "freshness": {
        "run_warn_hours": 36,        # cron diário: >36h = atrasou uma rodada
        "run_fail_hours": 72,        # >72h = pipeline parado
        "source_warn_days": 7,       # editais mais novos da fonte
        "source_fail_days": 21,
        "stuck_run_hours": 6,        # execução 'RUNNING' há mais que isso = travou
    },
    "volume": {
        "max_row_drop_pct": 10.0,         # queda do escopo vs execução anterior
        "max_uf_loss": 0,                 # UFs que sumiram vs execução anterior
        "checkpoint_max_lag_days": 30,    # fim da cobertura histórica vs hoje
        "min_items_coverage_pct": 80.0,   # editais no escopo com ≥1 item coletado
    },
    "distribution": {
        "max_zero_value_pct": 15.0,       # valor estimado nulo/zero
        "value_hard_cap": 1.0e10,         # R$ 10 bi: implausível para um edital
        "outlier_mad_z": 5.0,             # z robusto (log10) para outlier
        "max_outlier_pct": 2.0,
        "max_term_share_pct": 40.0,       # um termo respondendo por >40% dos matches
        "max_short_term_only_pct": 10.0,  # editais casados SÓ por termos curtos (≤3)
        "short_term_len": 3,
        "match_rate_shift_pp": 15.0,      # variação da taxa de match vs execução anterior
        "valid_ufs": [
            "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
            "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
        ],
        "modalidades_esperadas": [4, 6, 8, 12],
        "situacoes_conhecidas": [
            "Divulgada no PNCP", "Revogada", "Suspensa", "Anulada",
        ],
    },
    "schema": {
        "sample_size": 300,               # linhas recentes auditadas via raw_json
        "max_bad_record_pct": 1.0,        # % tolerado de registros com tipo inválido
    },
    "lineage": {
        "min_coverage_pct": 100.0,
    },
}

# ---------------------------------------------------------------------------
# Contrato da API PNCP (campos que o pipeline consome em db.upsert_contratacao)
# ---------------------------------------------------------------------------
API_CONTRACT: Dict[str, Any] = {
    # chave deve existir no registro (renomeação => ausente)
    "required_keys": {
        "numeroControlePNCP": "str", "anoCompra": "int", "sequencialCompra": "int",
        "numeroCompra": "str", "processo": "str", "objetoCompra": "str",
        "modalidadeId": "int", "modalidadeNome": "str", "situacaoCompraNome": "str",
        "valorTotalEstimado": "number", "valorTotalHomologado": "number",
        "dataPublicacaoPncp": "datetime", "dataEncerramentoProposta": "datetime",
        "dataAberturaProposta": "datetime",
        "orgaoEntidade": "dict", "unidadeOrgao": "dict",
        "srp": "bool", "linkSistemaOrigem": "str",
    },
    # além de existir, não pode ser nulo
    "non_null": ["numeroControlePNCP", "anoCompra", "sequencialCompra",
                 "modalidadeId", "dataPublicacaoPncp", "orgaoEntidade", "unidadeOrgao"],
    "nested": {
        "orgaoEntidade": {"cnpj": "str", "razaoSocial": "str"},
        "unidadeOrgao": {"ufSigla": "str", "municipioNome": "str"},
    },
    # campos já vistos na API (qualquer outro = campo novo => aviso de drift)
    "known_fields": [
        "valorTotalHomologado", "orgaoEntidade", "dataInclusao", "dataAtualizacao", "anoCompra", "srp",
        "sequencialCompra", "emendaParlamentar", "numeroCompra", "processo", "objetoCompra",
        "informacaoComplementar", "dataAberturaProposta", "dataEncerramentoProposta", "dataPublicacaoPncp",
        "dataAtualizacaoGlobal", "unidadeOrgao", "orgaoSubRogado", "unidadeSubRogada", "amparoLegal",
        "linkSistemaOrigem", "linkProcessoEletronico", "justificativaPresencial", "numeroControlePNCP",
        "valorTotalEstimado", "modalidadeId", "modalidadeNome", "modoDisputaId", "modoDisputaNome",
        "tipoInstrumentoConvocatorioCodigo", "tipoInstrumentoConvocatorioNome", "fontesOrcamentarias",
        "situacaoCompraId", "situacaoCompraNome", "usuarioNome",
    ],
}

EXPECTED_DB_COLUMNS = {
    "id", "numero_controle_pncp", "ano_compra", "sequencial_compra", "numero_compra", "processo",
    "cnpj_orgao", "razao_social_orgao", "esfera_id", "poder_id", "uf_sigla", "municipio_nome",
    "codigo_unidade", "nome_unidade", "modalidade_id", "modalidade_nome", "modo_disputa_nome",
    "situacao_compra_nome", "srp", "objeto_compra", "informacao_complementar",
    "valor_total_estimado", "valor_total_homologado", "data_publicacao_pncp",
    "data_abertura_proposta", "data_encerramento_proposta", "link_sistema_origem",
    "link_processo_eletronico", "matched_category", "matched_subtema", "matched_keywords",
    "raw_json", "created_at", "base_logistica", "distancia_km", "faixa_raio", "selo_logistico",
    "is_priority_geo", "briefing_ia_path", "pdf_paths",
    "first_run_id", "last_run_id", "source_endpoint", "keywords_hash", "classified_at",
}

# ---------------------------------------------------------------------------
# Manifesto de linhagem: da fonte ao indicador final (usado no dashboard)
# ---------------------------------------------------------------------------
LINEAGE_STAGES: List[Dict[str, str]] = [
    {"etapa": "1. Fonte", "artefato": "API PNCP (/contratacoes/publicacao, /contratacoes/proposta)",
     "codigo": "pncp_client.py", "garantia": "Erro de API ≠ 'sem registros'; contrato de schema validado"},
    {"etapa": "2. Ingestão", "artefato": "Tabela contratacoes (raw_json preservado) + itens_contratacao",
     "codigo": "collector.py → db.upsert_contratacao", "garantia": "Carimbo por linha: run_id, endpoint, versão do dicionário"},
    {"etapa": "3. Classificação", "artefato": "matched_category / matched_subtema / matched_keywords",
     "codigo": "matcher.py + config/keywords.yaml", "garantia": "keywords_hash identifica a versão do dicionário usada"},
    {"etapa": "4. Higienização", "artefato": "valor_total_estimado ajustado (+ valor_estimado_original, regra_higienizacao)",
     "codigo": "analytics.higienizar_valores", "garantia": "Regra aplicada e valor original ficam registrados por linha"},
    {"etapa": "5. Indicador", "artefato": "KPIs, Score de candidatura (0-100), matriz risco×retorno",
     "codigo": "analytics.summary_kpis / live_candidacy_radar", "garantia": "Pesos de decisão são parâmetros do painel (sidebar)"},
]

INDICATOR_LINEAGE: List[Dict[str, str]] = [
    {"indicador": "Editais indexados / Valor mapeado",
     "cadeia": "contratacoes → filtro matched_category ≠ '' → soma de valor_total_estimado (higienizado)"},
    {"indicador": "Score de candidatura",
     "cadeia": "contratacoes (abertos) → aderência(matched_subtema/objeto) + custo-benefício(valor, prazo) + logística(base, distância) + histórico → pesos da sidebar"},
    {"indicador": "Risco × Retorno",
     "cadeia": "Score de candidatura → calcular_risco_retorno (modalidade, prazo, logística, valor)"},
    {"indicador": "Mapa / Bases logísticas",
     "cadeia": "uf_sigla + municipio_nome → core/geo_utils.GeoIntelligence → distancia_km, base_logistica"},
]


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_ts(value: Any) -> Optional[datetime]:
    """Interpreta 'YYYY-MM-DD HH:MM:SS' ou ISO 8601; naive é tratado como UTC."""
    if value is None or value == "":
        return None
    s = str(value).strip().replace("Z", "")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        try:
            dt = datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _deep_merge(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _validate_types(default: Dict[str, Any], over: Dict[str, Any], path: str = "") -> None:
    for k, v in (over or {}).items():
        if k not in default:
            raise ValueError(f"observability.yaml: chave desconhecida '{path}{k}'")
        d = default[k]
        if isinstance(d, dict):
            if not isinstance(v, dict):
                raise ValueError(f"observability.yaml: '{path}{k}' deve ser um mapa")
            _validate_types(d, v, f"{path}{k}.")
        elif isinstance(d, (int, float)) and not isinstance(d, bool):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError(
                    f"observability.yaml: '{path}{k}' deve ser numérico, veio {v!r} "
                    f"(dica: PyYAML lê 1e10 como texto; use 1.0e+10 ou o inteiro por extenso)")


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    cfg_path = Path(path or DEFAULT_CONFIG_PATH)
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            override = yaml.safe_load(f) or {}
        _validate_types(DEFAULT_CONFIG, override)
        return _deep_merge(DEFAULT_CONFIG, override)
    return DEFAULT_CONFIG


def parse_keywords(raw: Any) -> List[str]:
    """Lê matched_keywords nos dois formatos já gravados ('a, b' e JSON '["a","b"]')."""
    if raw is None:
        return []
    s = str(raw).strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            return [str(t) for t in json.loads(s)]
        except ValueError:
            pass
    return [t.strip() for t in s.split(",") if t.strip()]


def current_git_sha() -> Optional[str]:
    sha = os.getenv("GITHUB_SHA")
    if sha:
        return sha[:10]
    try:
        out = subprocess.run(["git", "rev-parse", "--short=10", "HEAD"], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except Exception:
        return None


@dataclass
class CheckResult:
    pillar: str
    name: str
    status: str            # PASS | WARN | FAIL | SKIP
    observed: str = ""
    expected: str = ""
    detail: str = ""


# ---------------------------------------------------------------------------
# SCHEMA: auditoria do contrato da API (usada na ingestão e na verificação pós-fato)
# ---------------------------------------------------------------------------
def _type_ok(value: Any, kind: str) -> bool:
    if value is None:
        return True  # nulidade é tratada à parte (non_null)
    if kind == "str":
        return isinstance(value, str)
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "dict":
        return isinstance(value, dict)
    if kind == "datetime":
        return isinstance(value, str) and parse_ts(value) is not None
    return True


class ContractAudit:
    """Acumula violações do contrato da API em registros brutos (antes do upsert)."""

    def __init__(self, contract: Optional[Dict[str, Any]] = None):
        self.contract = contract or API_CONTRACT
        self.records = 0
        self.missing: Dict[str, int] = {}
        self.null_required: Dict[str, int] = {}
        self.type_errors: Dict[str, int] = {}
        self.bad_records = 0
        self.observed_fields: set = set()

    def _bump(self, bucket: Dict[str, int], key: str) -> None:
        bucket[key] = bucket.get(key, 0) + 1

    def add(self, records: Iterable[Dict[str, Any]]) -> None:
        required = self.contract["required_keys"]
        non_null = set(self.contract["non_null"])
        nested = self.contract["nested"]
        for rec in records:
            if not isinstance(rec, dict):
                continue
            self.records += 1
            self.observed_fields.update(rec.keys())
            bad = False
            for field, kind in required.items():
                if field not in rec:
                    self._bump(self.missing, field)
                    bad = True
                    continue
                val = rec[field]
                if val is None and field in non_null:
                    self._bump(self.null_required, field)
                    bad = True
                elif not _type_ok(val, kind):
                    self._bump(self.type_errors, field)
                    bad = True
            for parent, children in nested.items():
                sub = rec.get(parent)
                if not isinstance(sub, dict):
                    continue
                for child, kind in children.items():
                    key = f"{parent}.{child}"
                    if child not in sub:
                        self._bump(self.missing, key)
                        bad = True
                    elif not _type_ok(sub[child], kind):
                        self._bump(self.type_errors, key)
                        bad = True
            if bad:
                self.bad_records += 1

    @property
    def new_fields(self) -> List[str]:
        return sorted(self.observed_fields - set(self.contract["known_fields"]) - set(self.contract["required_keys"]))

    @property
    def disappeared_fields(self) -> List[str]:
        return sorted(set(self.contract["known_fields"]) - self.observed_fields) if self.records else []

    def fields_hash(self) -> str:
        return hashlib.sha256(json.dumps(sorted(self.observed_fields)).encode()).hexdigest()[:12]

    def status(self, max_bad_pct: float = 1.0) -> str:
        if not self.records:
            return "SKIP"
        if self.missing or self.null_required:
            return "FAIL"
        if self.type_errors and (self.bad_records / self.records * 100) > max_bad_pct:
            return "FAIL"
        if self.type_errors or self.new_fields:
            return "WARN"
        return "PASS"

    def summary(self) -> Dict[str, Any]:
        return {
            "records": self.records,
            "bad_records": self.bad_records,
            "missing_required": self.missing,
            "null_required": self.null_required,
            "type_errors": self.type_errors,
            "new_fields": self.new_fields,
            "disappeared_fields": self.disappeared_fields,
            "fields_hash": self.fields_hash(),
        }


# ---------------------------------------------------------------------------
# LINEAGE/FRESHNESS: registro de execuções do pipeline
# ---------------------------------------------------------------------------
class RunTracker:
    """Registra cada execução do pipeline em `pipeline_runs` (e snapshots de schema)."""

    def __init__(self, db, trigger: str = "manual"):
        self.db = db
        self.trigger = trigger
        self.run_id: Optional[str] = None

    def start(self, keywords_hash: str = "") -> str:
        self.run_id = f"{utcnow().strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:4]}"
        with self.db.get_connection() as conn:
            conn.execute(
                "INSERT INTO pipeline_runs (run_id, trigger, started_at, status, git_sha, keywords_hash) "
                "VALUES (?, ?, ?, 'RUNNING', ?, ?)",
                (self.run_id, self.trigger, _ts(utcnow()), current_git_sha(), keywords_hash),
            )
            conn.commit()
        return self.run_id

    def finish(
        self,
        audits: Optional[Dict[str, ContractAudit]] = None,
        rows_scanned: int = 0,
        rows_matched: int = 0,
        api_errors: int = 0,
        failed_chunks: int = 0,
        error: Optional[str] = None,
        max_bad_pct: float = 1.0,
    ) -> str:
        """Fecha a execução. Retorna o status: SUCCESS | DEGRADED | FAILED."""
        if not self.run_id:
            raise RuntimeError("RunTracker.finish() chamado antes de start().")
        audits = audits or {}
        contract_status = [a.status(max_bad_pct) for a in audits.values()]

        if error:
            status = "FAILED"
        elif "FAIL" in contract_status or api_errors > 0 or failed_chunks > 0:
            status = "DEGRADED"
        else:
            status = "SUCCESS"

        notes: Dict[str, Any] = {"contract": {ep: a.summary() for ep, a in audits.items()}}
        if error:
            notes["error"] = error

        with self.db.get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM contratacoes").fetchone()[0]
            matched = conn.execute(
                "SELECT COUNT(*) FROM contratacoes WHERE COALESCE(matched_category,'') != ''"
            ).fetchone()[0]
            uf_rows = conn.execute(
                "SELECT uf_sigla, COUNT(*) FROM contratacoes "
                "WHERE COALESCE(matched_category,'') != '' AND uf_sigla IS NOT NULL GROUP BY uf_sigla"
            ).fetchall()
            conn.execute(
                """UPDATE pipeline_runs SET finished_at=?, status=?, rows_scanned=?, rows_matched=?,
                   api_errors=?, failed_chunks=?, rows_total_after=?, rows_matched_after=?,
                   uf_counts=?, notes=? WHERE run_id=?""",
                (_ts(utcnow()), status, rows_scanned, rows_matched, api_errors, failed_chunks,
                 total, matched, json.dumps({r[0]: r[1] for r in uf_rows}),
                 json.dumps(notes, ensure_ascii=False), self.run_id),
            )
            for ep, audit in audits.items():
                conn.execute(
                    "INSERT INTO schema_snapshots (run_id, endpoint, captured_at, fields_hash, fields_json, records_seen) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (self.run_id, ep, _ts(utcnow()), audit.fields_hash(),
                     json.dumps(sorted(audit.observed_fields)), audit.records),
                )
            conn.commit()
        return status


# ---------------------------------------------------------------------------
# Avaliação dos 5 pilares
# ---------------------------------------------------------------------------
class HealthEvaluator:
    def __init__(self, db_path: str = DEFAULT_DB_PATH, config: Optional[Dict[str, Any]] = None,
                 keywords_path: str = DEFAULT_KEYWORDS_PATH, now: Optional[datetime] = None):
        self.db_path = db_path
        self.cfg = config or load_config()
        self.keywords_path = keywords_path
        self.now = now or utcnow()
        self.results: List[CheckResult] = []

        self.conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        self._tables = {r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self._cols = {r[1] for r in self.conn.execute("PRAGMA table_info(contratacoes)")} if "contratacoes" in self._tables else set()

    # -- helpers ------------------------------------------------------------
    def _add(self, pillar: str, name: str, status: str, observed: Any = "", expected: Any = "", detail: str = "") -> None:
        self.results.append(CheckResult(pillar, name, status, str(observed), str(expected), detail))

    def _scope_rows(self) -> List[sqlite3.Row]:
        """Escopo servido pelo painel: editais com matched_category preenchida."""
        if hasattr(self, "_scope_cache"):
            return self._scope_cache
        wanted = ["numero_controle_pncp", "uf_sigla", "modalidade_id", "situacao_compra_nome",
                  "valor_total_estimado", "data_publicacao_pncp", "data_encerramento_proposta",
                  "matched_category", "matched_keywords", "created_at",
                  "first_run_id", "last_run_id", "keywords_hash", "source_endpoint"]
        cols = ", ".join(c if c in self._cols else f"NULL AS {c}" for c in wanted)
        self._scope_cache = self.conn.execute(
            f"SELECT {cols} FROM contratacoes WHERE COALESCE(matched_category,'') != ''"
        ).fetchall()
        return self._scope_cache

    def _finished_runs(self, limit: int = 2) -> List[sqlite3.Row]:
        if "pipeline_runs" not in self._tables:
            return []
        return self.conn.execute(
            "SELECT * FROM pipeline_runs WHERE status IN ('SUCCESS','DEGRADED') "
            "ORDER BY finished_at DESC LIMIT ?", (limit,)
        ).fetchall()

    # -- FRESHNESS ----------------------------------------------------------
    def check_freshness(self) -> None:
        c = self.cfg["freshness"]
        runs = self._finished_runs(1)
        if runs:
            last = parse_ts(runs[0]["finished_at"])
            label, origem = "última execução", f"run {runs[0]['run_id']} ({runs[0]['status']})"
        else:
            row = self.conn.execute("SELECT MAX(created_at) FROM contratacoes").fetchone() if self._cols else None
            last = parse_ts(row[0]) if row else None
            label, origem = "último registro inserido", "proxy: sem pipeline_runs (created_at não muda em updates)"
        if last is None:
            self._add("Freshness", "execucao_recente", "FAIL", "sem dados", "execução registrada", "Nenhuma execução nem registro encontrados.")
        else:
            age_h = (self.now - last).total_seconds() / 3600
            st = "FAIL" if age_h > c["run_fail_hours"] else "WARN" if age_h > c["run_warn_hours"] else "PASS"
            self._add("Freshness", "execucao_recente", st, f"{age_h:.0f} h ({label}: {_ts(last)} UTC)",
                      f"≤ {c['run_warn_hours']} h", origem)

        stuck = []
        if "pipeline_runs" in self._tables:
            stuck = self.conn.execute("SELECT run_id, started_at FROM pipeline_runs WHERE status='RUNNING'").fetchall()
        stuck = [r for r in stuck if (parse_ts(r["started_at"]) or self.now) < self.now - timedelta(hours=c["stuck_run_hours"])]
        if stuck:
            self._add("Freshness", "execucao_travada", "WARN", f"{len(stuck)} run(s) RUNNING",
                      f"< {c['stuck_run_hours']} h", ", ".join(r["run_id"] for r in stuck[:3]))
        elif "pipeline_runs" in self._tables:
            self._add("Freshness", "execucao_travada", "PASS", "0", "0")

        pubs = [parse_ts(r["data_publicacao_pncp"]) for r in self._scope_rows()]
        pubs = [p for p in pubs if p]
        if not pubs:
            self._add("Freshness", "dado_mais_recente_na_fonte", "SKIP", "sem datas", "", "Escopo vazio.")
        else:
            age_d = (self.now - max(pubs)).days
            st = "FAIL" if age_d > c["source_fail_days"] else "WARN" if age_d > c["source_warn_days"] else "PASS"
            self._add("Freshness", "dado_mais_recente_na_fonte", st, f"{age_d} dias (edital mais novo: {max(pubs):%Y-%m-%d})",
                      f"≤ {c['source_warn_days']} dias", "Publicação mais recente no escopo servido.")

    # -- VOLUME -------------------------------------------------------------
    def check_volume(self) -> None:
        c = self.cfg["volume"]
        scope = self._scope_rows()
        runs = self._finished_runs(2)

        # 1) variação do escopo vs execução anterior
        if len(runs) == 2 and runs[1]["rows_matched_after"]:
            base, cur = runs[1]["rows_matched_after"], len(scope)
            drop = (base - cur) / base * 100
            dict_changed = (runs[0]["keywords_hash"] != runs[1]["keywords_hash"]) if ("keywords_hash" in runs[0].keys() and "keywords_hash" in runs[1].keys()) else False
            if drop > c["max_row_drop_pct"]:
                st = "WARN" if dict_changed else "FAIL"
            else:
                st = "PASS"
            det = f"Comparado à execução {runs[1]['run_id']}." + (" (dicionário alterado)" if dict_changed else "")
            self._add("Volume", "variacao_do_escopo", st, f"{cur} (antes: {base}; Δ {-drop:+.1f}%)",
                      f"queda ≤ {c['max_row_drop_pct']}%", det)
        else:
            self._add("Volume", "variacao_do_escopo", "SKIP", len(scope), "", "Precisa de ≥ 2 execuções registradas para ter baseline.")

        # 2) cobertura de UFs vs execução anterior
        cur_ufs = {r["uf_sigla"] for r in scope if r["uf_sigla"]}
        if len(runs) == 2 and runs[1]["uf_counts"]:
            prev_ufs = set(json.loads(runs[1]["uf_counts"]))
            lost = sorted(prev_ufs - cur_ufs)
            dict_changed = (runs[0]["keywords_hash"] != runs[1]["keywords_hash"]) if ("keywords_hash" in runs[0].keys() and "keywords_hash" in runs[1].keys()) else False
            st = "WARN" if (len(lost) > c["max_uf_loss"] and dict_changed) else ("FAIL" if len(lost) > c["max_uf_loss"] else "PASS")
            det = f"Comparado à execução {runs[1]['run_id']}." + (" (dicionário alterado)" if dict_changed else "")
            self._add("Volume", "cobertura_de_ufs", st, f"{len(cur_ufs)} UFs (perdeu: {', '.join(lost) or 'nenhuma'})",
                      f"perdas ≤ {c['max_uf_loss']}", det)
        else:
            self._add("Volume", "cobertura_de_ufs", "SKIP", f"{len(cur_ufs)} UFs", "", "Sem baseline de UFs (precisa de ≥ 2 execuções).")

        # 3) cobertura histórica por checkpoints
        if "crawler_checkpoints" in self._tables:
            cps = self.conn.execute(
                "SELECT modalidade_id, data_inicial, data_final FROM crawler_checkpoints WHERE status='COMPLETED' "
                "ORDER BY modalidade_id, data_inicial").fetchall()
        else:
            cps = []
        if not cps:
            self._add("Volume", "cobertura_historica", "SKIP", "sem checkpoints", "", "Nenhuma coleta histórica registrada.")
        else:
            gaps: List[str] = []
            last_end = None
            by_mod: Dict[int, List[Tuple[datetime, datetime]]] = {}
            for r in cps:
                by_mod.setdefault(r["modalidade_id"], []).append(
                    (datetime.strptime(r["data_inicial"], "%Y%m%d"), datetime.strptime(r["data_final"], "%Y%m%d")))
            for mod, spans in by_mod.items():
                prev_end = None
                for ini, fim in spans:
                    if prev_end and ini > prev_end + timedelta(days=1):
                        gaps.append(f"mod {mod}: {prev_end:%Y-%m-%d} → {ini:%Y-%m-%d}")
                    prev_end = max(prev_end, fim) if prev_end else fim
                last_end = max(last_end, prev_end) if last_end else prev_end
            lag = (self.now - last_end).days
            problems = []
            if gaps:
                problems.append(f"{len(gaps)} buraco(s): {'; '.join(gaps[:3])}")
            if lag > c["checkpoint_max_lag_days"]:
                problems.append(f"cobertura histórica termina em {last_end:%Y-%m-%d} ({lag} dias atrás)")
            self._add("Volume", "cobertura_historica", "WARN" if problems else "PASS",
                      f"até {last_end:%Y-%m-%d} (defasagem {lag} d)", f"defasagem ≤ {c['checkpoint_max_lag_days']} d, sem buracos",
                      " | ".join(problems) or "Blocos contíguos e recentes.")

        # 4) erros de ingestão na última execução
        if "pipeline_runs" in self._tables:
            last = self.conn.execute(
                "SELECT run_id, status, api_errors, failed_chunks FROM pipeline_runs WHERE status != 'RUNNING' "
                "ORDER BY started_at DESC LIMIT 1").fetchone()
            if last:
                bad = (last["api_errors"] or 0) + (last["failed_chunks"] or 0)
                st = "FAIL" if last["status"] == "FAILED" else "WARN" if bad else "PASS"
                self._add("Volume", "erros_de_ingestao", st,
                          f"{last['api_errors'] or 0} erros de API, {last['failed_chunks'] or 0} blocos não gravados ({last['status']})",
                          "0", f"Execução {last['run_id']}. Blocos com falha NÃO viram checkpoint e serão recoletados.")
            else:
                self._add("Volume", "erros_de_ingestao", "SKIP", "sem execuções", "")

        # 5) itens coletados para editais no escopo
        if scope and "itens_contratacao" in self._tables:
            with_items = self.conn.execute(
                "SELECT COUNT(DISTINCT c.numero_controle_pncp) FROM contratacoes c "
                "JOIN itens_contratacao i ON i.numero_controle_pncp = c.numero_controle_pncp "
                "WHERE COALESCE(c.matched_category,'') != ''").fetchone()[0]
            pct = with_items / len(scope) * 100
            st = "WARN" if pct < c["min_items_coverage_pct"] else "PASS"
            self._add("Volume", "cobertura_de_itens", st, f"{pct:.0f}% ({with_items}/{len(scope)})", f"≥ {c['min_items_coverage_pct']}%",
                      "Itens só são coletados no momento do match; editais reclassificados depois ficam sem itens/briefing.")

        # 6) itens órfãos
        if "itens_contratacao" in self._tables and self._cols:
            orphans = self.conn.execute(
                "SELECT COUNT(*) FROM itens_contratacao i LEFT JOIN contratacoes c "
                "ON c.numero_controle_pncp = i.numero_controle_pncp WHERE c.id IS NULL").fetchone()[0]
            self._add("Volume", "itens_orfaos", "WARN" if orphans else "PASS", orphans, 0)

    # -- DISTRIBUTION -------------------------------------------------------
    def check_distribution(self) -> None:
        c = self.cfg["distribution"]
        scope = self._scope_rows()
        if not scope:
            self._add("Distribution", "escopo", "FAIL", "0 editais no escopo", "> 0", "O painel ficaria vazio.")
            return
        n = len(scope)

        # 1) valores inválidos / zerados
        vals = [r["valor_total_estimado"] for r in scope]
        neg = sum(1 for v in vals if v is not None and v < 0)
        zero = sum(1 for v in vals if v is None or v == 0)
        zero_pct = zero / n * 100
        st = "FAIL" if neg else "WARN" if zero_pct > c["max_zero_value_pct"] else "PASS"
        self._add("Distribution", "valor_estimado_valido", st, f"{neg} negativos; {zero_pct:.1f}% nulos/zero",
                  f"0 negativos; zero ≤ {c['max_zero_value_pct']}%",
                  "Valor zero = sigiloso/'sob demanda' no PNCP; o painel os trata como 'Valor sob Demanda'.")

        # 2) outliers (hard cap + z robusto em log10)
        pos = sorted(v for v in vals if v and v > 0)
        over_cap = sum(1 for v in pos if v > c["value_hard_cap"])
        outliers = 0
        if len(pos) >= 20:
            logs = [math.log10(v) for v in pos]
            med = logs[len(logs) // 2]
            mad = sorted(abs(x - med) for x in logs)[len(logs) // 2] * 1.4826
            if mad > 0:
                outliers = sum(1 for x in logs if abs(x - med) / mad > c["outlier_mad_z"])
        out_pct = outliers / max(len(pos), 1) * 100
        st = "FAIL" if over_cap else "WARN" if out_pct > c["max_outlier_pct"] else "PASS"
        self._add("Distribution", "valor_estimado_outliers", st,
                  f"{over_cap} acima de R$ {c['value_hard_cap']:,.0f}; {outliers} outliers ({out_pct:.1f}%)",
                  f"0 acima do teto; outliers ≤ {c['max_outlier_pct']}%",
                  f"Mediana ≈ R$ {10 ** (sorted(math.log10(v) for v in pos)[len(pos)//2]):,.0f}" if pos else "")

        # 3) coerência de datas
        future = inverted = 0
        examples: List[str] = []
        for r in scope:
            pub, enc = parse_ts(r["data_publicacao_pncp"]), parse_ts(r["data_encerramento_proposta"])
            if pub and pub > self.now + timedelta(days=1):
                future += 1
                examples.append(f"{r['numero_controle_pncp']} (publicação futura)")
            if pub and enc and enc < pub:
                inverted += 1
                if len(examples) < 3:
                    examples.append(f"{r['numero_controle_pncp']} (encerra {enc:%Y-%m-%d} < publica {pub:%Y-%m-%d})")
        st = "FAIL" if future else "WARN" if inverted else "PASS"
        self._add("Distribution", "datas_coerentes", st, f"{future} publicações no futuro; {inverted} encerramentos antes da publicação", "0 / 0",
                  "Exemplos: " + "; ".join(examples[:3]) if examples else "")

        # 4) domínio de UF
        valid = set(c["valid_ufs"])
        bad_ufs = sorted({r["uf_sigla"] for r in scope if r["uf_sigla"] and r["uf_sigla"] not in valid})
        nulls = sum(1 for r in scope if not r["uf_sigla"])
        st = "FAIL" if bad_ufs else "WARN" if nulls else "PASS"
        self._add("Distribution", "dominio_uf", st, f"inválidas: {bad_ufs or 'nenhuma'}; sem UF: {nulls}", "27 UFs válidas")

        # 5) domínio de modalidade / situação (categoria nova na fonte)
        mods = sorted({r["modalidade_id"] for r in scope if r["modalidade_id"] is not None} - set(c["modalidades_esperadas"]))
        sits = sorted({r["situacao_compra_nome"] for r in scope if r["situacao_compra_nome"]} - set(c["situacoes_conhecidas"]))
        self._add("Distribution", "dominio_categorias", "WARN" if (mods or sits) else "PASS",
                  f"modalidades novas: {mods or 'nenhuma'}; situações novas: {sits or 'nenhuma'}", "domínios conhecidos")

        # 6) viés do dicionário: concentração e termos curtos ambíguos
        term_count: Dict[str, int] = {}
        short_only = 0
        short_len = c["short_term_len"]
        short_terms: Dict[str, int] = {}
        for r in scope:
            terms = parse_keywords(r["matched_keywords"])
            for t in set(terms):
                term_count[t] = term_count.get(t, 0) + 1
            if terms and all(len(t) <= short_len for t in terms):
                short_only += 1
                for t in set(terms):
                    short_terms[t] = short_terms.get(t, 0) + 1
        if term_count:
            top, top_n = max(term_count.items(), key=lambda kv: kv[1])
            share = top_n / n * 100
            self._add("Distribution", "concentracao_de_termos", "WARN" if share > c["max_term_share_pct"] else "PASS",
                      f"'{top}' em {share:.0f}% dos editais", f"≤ {c['max_term_share_pct']}%")
            short_pct = short_only / n * 100
            top_short = ", ".join(f"{t}×{k}" for t, k in sorted(short_terms.items(), key=lambda kv: -kv[1])[:5])
            self._add("Distribution", "termos_curtos_ambiguos", "WARN" if short_pct > c["max_short_term_only_pct"] else "PASS",
                      f"{short_pct:.0f}% dos editais casados só por termos ≤{short_len} letras ({top_short or '—'})",
                      f"≤ {c['max_short_term_only_pct']}%",
                      "Siglas curtas (ia, bi, ava) geram falsos positivos; considere exigir 2 termos ou contexto.")
        else:
            self._add("Distribution", "concentracao_de_termos", "SKIP", "sem termos", "", "matched_keywords vazio.")

        # 7) taxa de match vs execução anterior
        runs = self._finished_runs(2)
        if len(runs) == 2 and runs[1]["rows_total_after"] and runs[0]["rows_total_after"]:
            rate = lambda r: r["rows_matched_after"] / r["rows_total_after"] * 100  # noqa: E731
            shift = rate(runs[0]) - rate(runs[1])
            self._add("Distribution", "taxa_de_match", "WARN" if abs(shift) > c["match_rate_shift_pp"] else "PASS",
                      f"{rate(runs[0]):.1f}% (antes {rate(runs[1]):.1f}%; Δ {shift:+.1f} p.p.)",
                      f"|Δ| ≤ {c['match_rate_shift_pp']} p.p.", "Mudança grande indica dicionário ou fonte alterados.")
        else:
            self._add("Distribution", "taxa_de_match", "SKIP", "", "", "Precisa de ≥ 2 execuções registradas.")

    # -- SCHEMA -------------------------------------------------------------
    def check_schema(self) -> None:
        c = self.cfg["schema"]
        missing = sorted(EXPECTED_DB_COLUMNS - self._cols)
        extra = sorted(self._cols - EXPECTED_DB_COLUMNS)
        self._add("Schema", "schema_do_banco", "FAIL" if missing else "PASS",
                  f"{len(self._cols)} colunas; faltando: {missing or 'nenhuma'}", "todas as esperadas",
                  f"Colunas extras: {extra}" if extra else "")

        if "raw_json" in self._cols:
            rows = self.conn.execute("SELECT raw_json FROM contratacoes ORDER BY id DESC LIMIT ?", (c["sample_size"],)).fetchall()
            records = []
            for r in rows:
                try:
                    records.append(json.loads(r["raw_json"]))
                except (TypeError, ValueError):
                    pass
            audit = ContractAudit()
            audit.add(records)
            parse_fail = len(rows) - len(records)
            st = audit.status(c["max_bad_record_pct"])
            if parse_fail:
                st = "FAIL"
            detail = json.dumps({k: v for k, v in audit.summary().items()
                                 if v and k in ("missing_required", "null_required", "type_errors", "new_fields", "disappeared_fields")},
                                ensure_ascii=False)
            self._add("Schema", "contrato_da_api", st,
                      f"{audit.records} registros auditados; {audit.bad_records} fora do contrato; {parse_fail} raw_json ilegível",
                      "0 campos ausentes/nulos/tipo inválido", detail if detail != "{}" else "Contrato respeitado.")

        if "schema_snapshots" in self._tables:
            snaps = self.conn.execute(
                "SELECT endpoint, run_id, fields_hash, fields_json FROM schema_snapshots ORDER BY id DESC").fetchall()
            drifts = []
            by_ep: Dict[str, List[sqlite3.Row]] = {}
            for s in snaps:
                by_ep.setdefault(s["endpoint"], []).append(s)
            for ep, lst in by_ep.items():
                if len(lst) >= 2 and lst[0]["fields_hash"] != lst[1]["fields_hash"]:
                    a, b = set(json.loads(lst[0]["fields_json"])), set(json.loads(lst[1]["fields_json"]))
                    drifts.append(f"{ep}: +{sorted(a - b)} -{sorted(b - a)}")
            if drifts:
                self._add("Schema", "drift_entre_execucoes", "WARN", f"{len(drifts)} endpoint(s) mudaram", "estável", " | ".join(drifts))
            elif any(len(v) >= 2 for v in by_ep.values()):
                self._add("Schema", "drift_entre_execucoes", "PASS", "campos idênticos", "estável")
            else:
                self._add("Schema", "drift_entre_execucoes", "SKIP", "", "", "Precisa de ≥ 2 snapshots por endpoint.")

    # -- LINEAGE ------------------------------------------------------------
    def check_lineage(self) -> None:
        c = self.cfg["lineage"]
        scope = self._scope_rows()
        if not scope:
            self._add("Lineage", "cobertura_de_linhagem", "SKIP", "escopo vazio")
            return
        n = len(scope)
        stamped = sum(1 for r in scope if r["last_run_id"] and r["keywords_hash"] and r["source_endpoint"])
        pct = stamped / n * 100
        self._add("Lineage", "cobertura_de_linhagem", "WARN" if pct < c["min_coverage_pct"] else "PASS",
                  f"{pct:.0f}% ({stamped}/{n})", f"≥ {c['min_coverage_pct']}%",
                  "Linhas sem run_id/endpoint/versão do dicionário não são rastreáveis. Rode o rematch para carimbar.")

        try:
            from pncp_intelligence.src.matcher import ThematicMatcher
            current = ThematicMatcher(self.keywords_path).fingerprint()
        except Exception as exc:  # pragma: no cover
            self._add("Lineage", "dicionario_vigente", "SKIP", "", "", f"Dicionário ilegível: {exc}")
            current = None
        if current:
            stale = [r for r in scope if r["keywords_hash"] and r["keywords_hash"] != current]
            self._add("Lineage", "dicionario_vigente", "WARN" if stale else "PASS",
                      f"{len(stale)} editais classificados com dicionário antigo (vigente: {current})", "0",
                      "keywords.yaml mudou depois da classificação; rode `python -m pncp_intelligence.src.rematch`." if stale else "")

        mixed = sum(1 for r in scope if str(r["matched_keywords"] or "").startswith("["))
        self._add("Lineage", "formato_matched_keywords", "WARN" if mixed else "PASS",
                  f"{mixed} linhas em formato JSON (padrão: 'a, b')", "0")

        if "pipeline_runs" in self._tables:
            known = {r[0] for r in self.conn.execute("SELECT run_id FROM pipeline_runs")} | {LEGACY_RUN_ID}
            orphan = sorted({r["last_run_id"] for r in scope if r["last_run_id"] and r["last_run_id"] not in known})
            self._add("Lineage", "runs_rastreaveis", "WARN" if orphan else "PASS",
                      f"{len(orphan)} run_id sem registro em pipeline_runs", "0", ", ".join(orphan[:3]))

    # -- API ----------------------------------------------------------------
    def run_all(self) -> "HealthReport":
        for fn in (self.check_freshness, self.check_volume, self.check_distribution, self.check_schema, self.check_lineage):
            try:
                fn()
            except Exception as exc:  # um check quebrado não pode derrubar o painel
                self._add(fn.__name__.replace("check_", "").capitalize(), fn.__name__, "FAIL",
                          f"check falhou: {type(exc).__name__}", "", str(exc)[:200])
        self.conn.close()
        return HealthReport(self.results, self.now)


class HealthReport:
    def __init__(self, results: List[CheckResult], now: datetime):
        self.results = results
        self.generated_at = now

    @property
    def overall(self) -> str:
        worst = max((_SEVERITY[r.status] for r in self.results), default=0)
        return {3: "FAIL", 2: "WARN"}.get(worst, "PASS")

    def counts(self) -> Dict[str, int]:
        out = {"PASS": 0, "SKIP": 0, "WARN": 0, "FAIL": 0}
        for r in self.results:
            out[r.status] += 1
        return out

    def by_pillar(self) -> Dict[str, str]:
        out = {}
        for p in PILLARS:
            sev = max((_SEVERITY[r.status] for r in self.results if r.pillar == p), default=0)
            out[p] = {3: "FAIL", 2: "WARN"}.get(sev, "PASS")
        return out

    def to_dicts(self) -> List[Dict[str, str]]:
        return [asdict(r) for r in self.results]

    def to_markdown(self) -> str:
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIP": "⏭️"}
        c = self.counts()
        lines = [f"## Observabilidade de dados — {icon[self.overall]} {self.overall}",
                 f"`{c['FAIL']}` FAIL · `{c['WARN']}` WARN · `{c['PASS']}` PASS · `{c['SKIP']}` SKIP "
                 f"— {self.generated_at:%Y-%m-%d %H:%M} UTC", "",
                 "| Pilar | Check | Status | Observado | Esperado |", "|---|---|---|---|---|"]
        for r in sorted(self.results, key=lambda x: (-_SEVERITY[x.status], PILLARS.index(x.pillar) if x.pillar in PILLARS else 9)):
            lines.append(f"| {r.pillar} | `{r.name}` | {icon[r.status]} {r.status} | {r.observed} | {r.expected} |")
        details = [r for r in self.results if r.status in ("WARN", "FAIL") and r.detail]
        if details:
            lines += ["", "### Detalhes"] + [f"- **{r.name}**: {r.detail}" for r in details]
        return "\n".join(lines)


def evaluate_health(db_path: str = DEFAULT_DB_PATH, config_path: Optional[str] = None,
                    keywords_path: str = DEFAULT_KEYWORDS_PATH, now: Optional[datetime] = None) -> HealthReport:
    """Avalia os 5 pilares em modo somente leitura (seguro para o dashboard)."""
    return HealthEvaluator(db_path, load_config(config_path), keywords_path, now).run_all()


def persist_report(db_path: str, report: HealthReport, run_id: Optional[str] = None) -> Optional[str]:
    """Grava o resultado em quality_checks (histórico). Usa a execução mais recente se run_id ausente."""
    conn = sqlite3.connect(db_path)
    try:
        if run_id is None:
            row = conn.execute("SELECT run_id FROM pipeline_runs ORDER BY started_at DESC LIMIT 1").fetchone()
            run_id = row[0] if row else None
        conn.executemany(
            "INSERT INTO quality_checks (run_id, checked_at, pillar, name, status, observed, expected, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(run_id, _ts(report.generated_at), r.pillar, r.name, r.status, r.observed, r.expected, r.detail)
             for r in report.results])
        conn.commit()
    finally:
        conn.close()
    return run_id


def lineage_for_edital(db_path: str, numero_controle: str) -> Dict[str, Any]:
    """Proveniência de um edital: execução, endpoint, dicionário, termos e execução original."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT numero_controle_pncp, source_endpoint, first_run_id, last_run_id, keywords_hash, classified_at, "
            "matched_category, matched_subtema, matched_keywords, created_at, link_sistema_origem "
            "FROM contratacoes WHERE numero_controle_pncp = ?", (numero_controle,)).fetchone()
        if not row:
            return {}
        out = dict(row)
        out["matched_keywords"] = parse_keywords(out["matched_keywords"])
        for key in ("first_run_id", "last_run_id"):
            run = conn.execute("SELECT started_at, status, git_sha FROM pipeline_runs WHERE run_id = ?", (out[key],)).fetchone() \
                if out[key] else None
            out[f"{key}_info"] = dict(run) if run else None
        return out
    finally:
        conn.close()


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Observabilidade de dados do pipeline PNCP (5 pilares).")
    ap.add_argument("--db", default=DEFAULT_DB_PATH)
    ap.add_argument("--config", default=None)
    ap.add_argument("--keywords", default=DEFAULT_KEYWORDS_PATH)
    ap.add_argument("--persist", action="store_true", help="grava o resultado em quality_checks")
    ap.add_argument("--gate", action="store_true", help="exit 1 se houver qualquer check FAIL")
    ap.add_argument("--markdown", action="store_true", help="imprime relatório em Markdown (ex.: GITHUB_STEP_SUMMARY)")
    ap.add_argument("--json", action="store_true", help="imprime relatório em JSON")
    args = ap.parse_args(argv)

    report = evaluate_health(args.db, args.config, args.keywords)
    if args.persist:
        persist_report(args.db, report)
    if args.json:
        print(json.dumps({"overall": report.overall, "checks": report.to_dicts()}, ensure_ascii=False, indent=2))
    else:
        print(report.to_markdown() if args.markdown else
              "\n".join(f"[{r.status:4}] {r.pillar:12} {r.name:28} {r.observed}" for r in report.results)
              + f"\n=> {report.overall}")
    return 1 if (args.gate and report.overall == "FAIL") else 0


if __name__ == "__main__":
    sys.exit(main())
