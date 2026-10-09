"""Gerenciamento do banco de dados relacional SQLite para o PNCP Intelligence.

Armazena editais, metadados, itens detalhados, categorizações temáticas e
checkpoints de coleta para permitir retomada segura e sem duplicações.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


class PNCPDatabase:
    def __init__(self, db_path: str = "pncp_intelligence/data/pncp_intelligence.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Tabela principal de contratações/editais
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS contratacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_controle_pncp TEXT UNIQUE,
                ano_compra INTEGER,
                sequencial_compra INTEGER,
                numero_compra TEXT,
                processo TEXT,
                cnpj_orgao TEXT,
                razao_social_orgao TEXT,
                esfera_id TEXT,
                poder_id TEXT,
                uf_sigla TEXT,
                municipio_nome TEXT,
                codigo_unidade TEXT,
                nome_unidade TEXT,
                modalidade_id INTEGER,
                modalidade_nome TEXT,
                modo_disputa_nome TEXT,
                situacao_compra_nome TEXT,
                srp INTEGER,
                objeto_compra TEXT,
                informacao_complementar TEXT,
                valor_total_estimado REAL,
                valor_total_homologado REAL,
                data_publicacao_pncp TEXT,
                data_abertura_proposta TEXT,
                data_encerramento_proposta TEXT,
                link_sistema_origem TEXT,
                link_processo_eletronico TEXT,
                matched_category TEXT,
                matched_subtema TEXT,
                matched_keywords TEXT,
                raw_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Tabela de itens da contratação
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS itens_contratacao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_controle_pncp TEXT,
                numero_item INTEGER,
                descricao TEXT,
                quantidade REAL,
                unidade_medida TEXT,
                valor_unitario_estimado REAL,
                valor_total_estimado REAL,
                valor_unitario_homologado REAL,
                valor_total_homologado REAL,
                situacao_item_nome TEXT,
                criterio_julgamento_nome TEXT,
                raw_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(numero_controle_pncp, numero_item)
            );
            """)

            # Tabela de checkpoints de coleta (evita reconsultar períodos já baixados)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawler_checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_inicial TEXT,
                data_final TEXT,
                modalidade_id INTEGER,
                total_registros INTEGER DEFAULT 0,
                total_matches INTEGER DEFAULT 0,
                status TEXT DEFAULT 'COMPLETED',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(data_inicial, data_final, modalidade_id)
            );
            """)

            # Índices de performance para relatórios e filtros analíticos
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contratacoes_uf ON contratacoes(uf_sigla);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contratacoes_data ON contratacoes(data_publicacao_pncp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contratacoes_modalidade ON contratacoes(modalidade_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contratacoes_categoria ON contratacoes(matched_category);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contratacoes_valor ON contratacoes(valor_total_estimado);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_itens_pncp ON itens_contratacao(numero_controle_pncp);")

            # Migração dinâmica de colunas logísticas e IA
            geo_columns = [
                ("base_logistica", "TEXT"),
                ("distancia_km", "REAL"),
                ("faixa_raio", "TEXT"),
                ("selo_logistico", "TEXT"),
                ("is_priority_geo", "INTEGER DEFAULT 0"),
                ("briefing_ia_path", "TEXT"),
                ("pdf_paths", "TEXT"),
            ]
            for col_name, col_type in geo_columns:
                try:
                    cursor.execute(f"ALTER TABLE contratacoes ADD COLUMN {col_name} {col_type};")
                except sqlite3.OperationalError:
                    pass

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contratacoes_base ON contratacoes(base_logistica);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_contratacoes_priority_geo ON contratacoes(is_priority_geo);")

            conn.commit()

    def is_chunk_completed(self, data_inicial: str, data_final: str, modalidade_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status FROM crawler_checkpoints 
                WHERE data_inicial = ? AND data_final = ? AND modalidade_id = ?
            """, (data_inicial, data_final, modalidade_id))
            row = cursor.fetchone()
            return row is not None and row["status"] == "COMPLETED"

    def record_checkpoint(self, data_inicial: str, data_final: str, modalidade_id: int, 
                          total_registros: int, total_matches: int) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO crawler_checkpoints (data_inicial, data_final, modalidade_id, total_registros, total_matches, status, updated_at)
                VALUES (?, ?, ?, ?, ?, 'COMPLETED', CURRENT_TIMESTAMP)
                ON CONFLICT(data_inicial, data_final, modalidade_id) DO UPDATE SET
                    total_registros = excluded.total_registros,
                    total_matches = excluded.total_matches,
                    status = 'COMPLETED',
                    updated_at = CURRENT_TIMESTAMP
            """, (data_inicial, data_final, modalidade_id, total_registros, total_matches))
            conn.commit()

    def upsert_contratacao(
        self,
        data: Dict[str, Any],
        matched_category: str = "", 
        matched_subtema: str = "",
        matched_keywords: str = "",
        geo_info: Optional[Dict[str, Any]] = None,
        briefing_ia_path: str = "",
        pdf_paths: Optional[List[str]] = None,
    ) -> bool:
        """Insere ou atualiza um edital no banco de dados com inteligência logística."""
        pncp_id = data.get("numeroControlePNCP")
        if not pncp_id:
            return False

        orgao = data.get("orgaoEntidade") or {}
        unidade = data.get("unidadeOrgao") or {}
        geo = geo_info or {}

        base_logistica = geo.get("base")
        distancia_km = geo.get("distancia_km")
        faixa_raio = geo.get("faixa_raio")
        selo_logistico = geo.get("selo")
        is_priority_geo = 1 if geo.get("is_priority_geo") else 0
        pdf_paths_json = json.dumps(pdf_paths or [], ensure_ascii=False)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO contratacoes (
                    numero_controle_pncp, ano_compra, sequencial_compra, numero_compra, processo,
                    cnpj_orgao, razao_social_orgao, esfera_id, poder_id,
                    uf_sigla, municipio_nome, codigo_unidade, nome_unidade,
                    modalidade_id, modalidade_nome, modo_disputa_nome, situacao_compra_nome,
                    srp, objeto_compra, informacao_complementar,
                    valor_total_estimado, valor_total_homologado,
                    data_publicacao_pncp, data_abertura_proposta, data_encerramento_proposta,
                    link_sistema_origem, link_processo_eletronico,
                    matched_category, matched_subtema, matched_keywords, raw_json,
                    base_logistica, distancia_km, faixa_raio, selo_logistico, is_priority_geo,
                    briefing_ia_path, pdf_paths
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?
                )
                ON CONFLICT(numero_controle_pncp) DO UPDATE SET
                    valor_total_estimado = COALESCE(excluded.valor_total_estimado, contratacoes.valor_total_estimado),
                    valor_total_homologado = COALESCE(excluded.valor_total_homologado, contratacoes.valor_total_homologado),
                    situacao_compra_nome = excluded.situacao_compra_nome,
                    matched_category = CASE WHEN excluded.matched_category != '' THEN excluded.matched_category ELSE contratacoes.matched_category END,
                    matched_subtema = CASE WHEN excluded.matched_subtema != '' THEN excluded.matched_subtema ELSE contratacoes.matched_subtema END,
                    matched_keywords = CASE WHEN excluded.matched_keywords != '' THEN excluded.matched_keywords ELSE contratacoes.matched_keywords END,
                    data_encerramento_proposta = excluded.data_encerramento_proposta,
                    raw_json = excluded.raw_json,
                    base_logistica = COALESCE(excluded.base_logistica, contratacoes.base_logistica),
                    distancia_km = COALESCE(excluded.distancia_km, contratacoes.distancia_km),
                    faixa_raio = COALESCE(excluded.faixa_raio, contratacoes.faixa_raio),
                    selo_logistico = COALESCE(excluded.selo_logistico, contratacoes.selo_logistico),
                    is_priority_geo = COALESCE(excluded.is_priority_geo, contratacoes.is_priority_geo),
                    briefing_ia_path = CASE WHEN excluded.briefing_ia_path != '' THEN excluded.briefing_ia_path ELSE contratacoes.briefing_ia_path END,
                    pdf_paths = CASE WHEN excluded.pdf_paths != '[]' THEN excluded.pdf_paths ELSE contratacoes.pdf_paths END
            """, (
                pncp_id,
                data.get("anoCompra"),
                data.get("sequencialCompra"),
                data.get("numeroCompra"),
                data.get("processo"),
                orgao.get("cnpj"),
                orgao.get("razaoSocial"),
                orgao.get("esferaId"),
                orgao.get("poderId"),
                unidade.get("ufSigla"),
                unidade.get("municipioNome"),
                unidade.get("codigoUnidade"),
                unidade.get("nomeUnidade"),
                data.get("modalidadeId"),
                data.get("modalidadeNome"),
                data.get("modoDisputaNome"),
                data.get("situacaoCompraNome"),
                1 if data.get("srp") else 0,
                data.get("objetoCompra"),
                data.get("informacaoComplementar"),
                data.get("valorTotalEstimado"),
                data.get("valorTotalHomologado"),
                data.get("dataPublicacaoPncp"),
                data.get("dataAberturaProposta"),
                data.get("dataEncerramentoProposta"),
                data.get("linkSistemaOrigem"),
                data.get("linkProcessoEletronico"),
                matched_category,
                matched_subtema,
                matched_keywords,
                json.dumps(data, ensure_ascii=False),
                base_logistica,
                distancia_km,
                faixa_raio,
                selo_logistico,
                is_priority_geo,
                briefing_ia_path,
                pdf_paths_json
            ))
            conn.commit()
            return True

    def insert_itens(self, pncp_id: str, itens: List[Dict[str, Any]]) -> int:
        """Insere ou atualiza os itens de um edital."""
        if not itens:
            return 0

        inserted = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for it in itens:
                cursor.execute("""
                    INSERT INTO itens_contratacao (
                        numero_controle_pncp, numero_item, descricao, quantidade, unidade_medida,
                        valor_unitario_estimado, valor_total_estimado,
                        valor_unitario_homologado, valor_total_homologado,
                        situacao_item_nome, criterio_julgamento_nome, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(numero_controle_pncp, numero_item) DO UPDATE SET
                        descricao = excluded.descricao,
                        quantidade = excluded.quantidade,
                        valor_unitario_estimado = excluded.valor_unitario_estimado,
                        valor_total_estimado = excluded.valor_total_estimado,
                        valor_unitario_homologado = excluded.valor_unitario_homologado,
                        valor_total_homologado = excluded.valor_total_homologado,
                        situacao_item_nome = excluded.situacao_item_nome,
                        criterio_julgamento_nome = excluded.criterio_julgamento_nome,
                        raw_json = excluded.raw_json
                """, (
                    pncp_id,
                    it.get("numeroItem"),
                    it.get("descricao"),
                    it.get("quantidade"),
                    it.get("unidadeMedida"),
                    it.get("valorUnitarioEstimado"),
                    it.get("valorTotalEstimado") or ((it.get("quantidade") or 0) * (it.get("valorUnitarioEstimado") or 0)),
                    it.get("valorUnitarioHomologado"),
                    it.get("valorTotalHomologado"),
                    it.get("situacaoItemNome"),
                    it.get("criterioJulgamentoNome"),
                    json.dumps(it, ensure_ascii=False)
                ))
                inserted += 1
            conn.commit()
        return inserted

    def get_stats(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) as total, sum(valor_total_estimado) as valor_total FROM contratacoes")
            row = cursor.fetchone()
            total_editais = row["total"] if row else 0
            valor_total = row["valor_total"] if row and row["valor_total"] else 0.0

            cursor.execute("SELECT count(*) as total_itens FROM itens_contratacao")
            total_itens = cursor.fetchone()["total_itens"]

            cursor.execute("""
                SELECT matched_category, count(*) as count 
                FROM contratacoes 
                GROUP BY matched_category 
                ORDER BY count DESC
            """)
            categorias = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT count(*) as total_checkpoints FROM crawler_checkpoints")
            total_checkpoints = cursor.fetchone()["total_checkpoints"]

            return {
                "total_editais": total_editais,
                "valor_total_estimado": valor_total,
                "total_itens": total_itens,
                "categorias": categorias,
                "total_checkpoints": total_checkpoints
            }
