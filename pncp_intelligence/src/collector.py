"""Coletor e orquestrador de ingestão de editais e demandas do PNCP.

Integra:
- Inteligência Logística com as 7 Bases e 149 Cidades Alvo (core/geo_utils.py).
- Download de PDFs e Termos de Referência (TR).
- Geração de Briefings estruturados para leitura e triagem por IA.
- Checkpointing para coleta contínua dos últimos 2 anos.
"""

import json
import logging
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.geo_utils import GeoIntelligence
from pncp_intelligence.src.db import PNCPDatabase
from pncp_intelligence.src.matcher import ThematicMatcher
from pncp_intelligence.src.pncp_client import PNCPClient

logger = logging.getLogger("PNCPCollector")


class PNCPCollector:
    def __init__(
        self,
        db: Optional[PNCPDatabase] = None,
        client: Optional[PNCPClient] = None,
        matcher: Optional[ThematicMatcher] = None,
        geo: Optional[GeoIntelligence] = None,
        chunk_days: int = 15,
        fetch_items_on_match: bool = True,
        download_pdfs: bool = False,
        briefing_dir: str = "pncp_intelligence/data/briefings_ia",
        pdf_dir: str = "pncp_intelligence/data/edital_docs",
    ):
        self.db = db or PNCPDatabase()
        self.client = client or PNCPClient()
        self.matcher = matcher or ThematicMatcher()
        self.geo = geo or GeoIntelligence()
        self.chunk_days = chunk_days
        self.fetch_items_on_match = fetch_items_on_match
        self.download_pdfs = download_pdfs
        self.briefing_dir = Path(briefing_dir)
        self.pdf_dir = Path(pdf_dir)

        self.briefing_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def generate_date_chunks(start_date: date, end_date: date, chunk_size: int = 15) -> List[tuple[str, str]]:
        """Divide o intervalo de datas em blocos de tamanho chunk_size no formato AAAAMMDD."""
        chunks = []
        cur_start = start_date
        while cur_start <= end_date:
            cur_end = min(cur_start + timedelta(days=chunk_size - 1), end_date)
            chunks.append((cur_start.strftime("%Y%m%d"), cur_end.strftime("%Y%m%d")))
            cur_start = cur_end + timedelta(days=1)
        return chunks

    def _generate_ai_briefing(
        self,
        item: Dict[str, Any],
        geo_info: Dict[str, Any],
        itens_detalhados: Optional[List[Dict[str, Any]]] = None,
        doc_links: Optional[List[str]] = None,
        downloaded_pdfs: Optional[List[str]] = None,
    ) -> str:
        """Gera o arquivo de briefing estruturado para consumo de LLMs / IA."""
        pncp_id = item.get("numeroControlePNCP") or f"{item.get('anoCompra')}_{item.get('sequencialCompra')}"
        clean_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(pncp_id))
        briefing_path = self.briefing_dir / f"briefing_{clean_id}.txt"

        orgao = item.get("orgaoEntidade") or {}
        unidade = item.get("unidadeOrgao") or {}
        orgao_nome = orgao.get("razaoSocial") or "Não informado"
        municipio = unidade.get("municipioNome") or ""
        uf = unidade.get("ufSigla") or ""
        modalidade = item.get("modalidadeNome") or "Não informada"
        objeto = item.get("objetoCompra") or ""
        valor = item.get("valorTotalEstimado") or item.get("valorEstimado") or 0.0

        if isinstance(valor, (int, float)) and valor > 0:
            valor_fmt = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            valor_fmt = "Não informado / Sigiloso"

        data_fim = item.get("dataEncerramentoProposta") or item.get("dataAberturaProposta") or "Ver Edital"
        link = item.get("linkSistemaOrigem") or f"https://pncp.gov.br/app/editais/{pncp_id}"

        with open(briefing_path, "w", encoding="utf-8") as f:
            f.write("PORTAL: PNCP (Portal Nacional de Contratações Públicas)\n")
            f.write(f"ÓRGÃO CONTRATANTE: {orgao_nome} ({municipio}/{uf})\n")
            f.write(f"MODALIDADE: {modalidade}\n")
            f.write(f"OBJETO DA CONTRATAÇÃO: {objeto}\n")
            f.write(f"VALOR ESTIMADO: {valor_fmt}\n")
            f.write(f"PRAZO PARA PROPOSTAS: {data_fim}\n")
            f.write(f"LINK OFICIAL: {link}\n")
            if geo_info.get("matched"):
                f.write(f"BASE LOGÍSTICA COMPATÍVEL: {geo_info.get('base')} ({geo_info.get('faixa_raio')})\n")
                f.write(f"SELO LOGÍSTICO: {geo_info.get('selo')}\n")
                f.write(f"DISTÂNCIA ESTIMADA DA BASE: {geo_info.get('distancia_km')} km\n")
            if doc_links:
                f.write("ARQUIVOS / ANEXOS OFICIAIS:\n" + "\n".join(doc_links) + "\n")
            if downloaded_pdfs:
                f.write("PDFS BAIXADOS LOCALMENTE:\n" + "\n".join(downloaded_pdfs) + "\n")

            if itens_detalhados:
                f.write("\nITENS DA CONTRATAÇÃO:\n")
                for it in itens_detalhados:
                    desc = it.get("descricao") or ""
                    qtd = it.get("quantidade") or 1
                    val_u = it.get("valorUnitarioEstimado") or 0.0
                    f.write(f"  - Item {it.get('numeroItem')}: {desc[:120]} | Qtd: {qtd} | R$ Unit: {val_u}\n")

            f.write("\nDADOS COMPLETOS EM JSON:\n")
            f.write(json.dumps(item, indent=2, ensure_ascii=False))

        return str(briefing_path)

    def _process_matched_edital(
        self,
        item: Dict[str, Any],
        cat_name: str,
        sub_name: str,
        terms: List[str]
    ) -> Tuple[int, List[str], str]:
        """Processa itens detalhados, checagem geográfica, PDFs e briefing para edital qualificado."""
        unidade = item.get("unidadeOrgao") or {}
        municipio = unidade.get("municipioNome")
        uf = unidade.get("ufSigla")
        objeto = item.get("objetoCompra") or ""

        # 1. Inteligência Geográfica
        geo_info = self.geo.match_localidade(municipio, uf, objeto_texto=objeto)

        # 2. Itens detalhados
        n_itens = 0
        itens = []
        orgao = item.get("orgaoEntidade") or {}
        cnpj = orgao.get("cnpj")
        ano = item.get("anoCompra")
        seq = item.get("sequencialCompra")
        pncp_id = item.get("numeroControlePNCP")

        if self.fetch_items_on_match and cnpj and ano and seq and pncp_id:
            itens = self.client.get_itens_compra(cnpj, ano, seq) or []
            if itens:
                n_itens = self.db.insert_itens(pncp_id, itens)

        # 3. Anexos e download de PDFs (se habilitado)
        downloaded_pdfs: List[str] = []
        doc_links: List[str] = []
        if cnpj and ano and seq:
            arquivos_meta = self.client.get_arquivos_compra(cnpj, ano, seq) or []
            for arq in arquivos_meta:
                seq_doc = arq.get("sequencialDocumento")
                nome_arq = arq.get("nomeArquivo") or f"doc_{seq_doc}.pdf"
                url_doc = arq.get("url") or f"{self.client.pncp_base_url}/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos/{seq_doc}"
                doc_links.append(f"{nome_arq}: {url_doc}")

                if self.download_pdfs and seq_doc:
                    safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", nome_arq)
                    dest_pdf = str(self.pdf_dir / f"{pncp_id}_{safe_name}")
                    if self.client.download_arquivo_binario(cnpj, ano, seq, seq_doc, dest_pdf):
                        downloaded_pdfs.append(dest_pdf)

        # 4. Geração do Briefing para IA
        briefing_path = self._generate_ai_briefing(
            item=item,
            geo_info=geo_info,
            itens_detalhados=itens,
            doc_links=doc_links,
            downloaded_pdfs=downloaded_pdfs,
        )

        # 5. Salva no banco de dados com selos e métricas logísticas
        self.db.upsert_contratacao(
            data=item,
            matched_category=cat_name,
            matched_subtema=sub_name,
            matched_keywords=", ".join(terms),
            geo_info=geo_info,
            briefing_ia_path=briefing_path,
            pdf_paths=downloaded_pdfs,
        )

        return n_itens, downloaded_pdfs, briefing_path

    def collect_period(
        self,
        start_date: date,
        end_date: date,
        modalidades: Optional[List[int]] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Executa a coleta histórica paginada em blocos para os últimos N meses/anos."""
        modalidades = modalidades or [6, 4, 8, 12]
        chunks = self.generate_date_chunks(start_date, end_date, self.chunk_days)

        total_scanned = 0
        total_matches = 0
        total_items_saved = 0

        logger.info(f"Iniciando coleta histórica de {start_date} até {end_date} em {len(chunks)} blocos...")

        for chunk_idx, (dt_ini, dt_fim) in enumerate(chunks, 1):
            for mod_id in modalidades:
                if self.db.is_chunk_completed(dt_ini, dt_fim, mod_id):
                    logger.debug(f"Bloco {dt_ini}-{dt_fim} (Modalidade {mod_id}) já coletado anteriormente. Ignorando.")
                    continue

                logger.info(f"[{chunk_idx}/{len(chunks)}] Coletando {dt_ini} a {dt_fim} | Modalidade {mod_id}...")

                chunk_scanned = 0
                chunk_matches = 0
                pagina = 1

                while True:
                    resp = self.client.get_publicacoes(
                        data_inicial=dt_ini,
                        data_final=dt_fim,
                        codigo_modalidade=mod_id,
                        pagina=pagina,
                        tamanho_pagina=50,
                    )

                    if not resp:
                        break

                    data_list = resp.get("data") or []
                    if not data_list:
                        break

                    for item in data_list:
                        chunk_scanned += 1
                        total_scanned += 1

                        objeto = item.get("objetoCompra") or ""
                        info = item.get("informacaoComplementar") or ""

                        is_match, cat_name, sub_name, terms = self.matcher.match(objeto, info)

                        if is_match:
                            chunk_matches += 1
                            total_matches += 1

                            n_itens, _, _ = self._process_matched_edital(item, cat_name, sub_name, terms)
                            total_items_saved += n_itens

                    total_paginas = resp.get("totalPaginas") or 1
                    paginas_restantes = resp.get("paginasRestantes") or 0

                    if pagina % 5 == 0 or paginas_restantes <= 0:
                        logger.info(f"   Página {pagina}/{total_paginas} (Restantes: {paginas_restantes}) | Matches acumulados: {chunk_matches}")

                    if pagina >= total_paginas or paginas_restantes <= 0:
                        break

                    pagina += 1

                self.db.record_checkpoint(dt_ini, dt_fim, mod_id, chunk_scanned, chunk_matches)

                if progress_callback:
                    progress_callback({
                        "chunk": f"{dt_ini}-{dt_fim}",
                        "modalidade": mod_id,
                        "chunk_scanned": chunk_scanned,
                        "chunk_matches": chunk_matches,
                        "total_scanned": total_scanned,
                        "total_matches": total_matches,
                        "total_items": total_items_saved,
                    })

        return {
            "total_scanned": total_scanned,
            "total_matches": total_matches,
            "total_items_saved": total_items_saved,
        }

    def collect_live_opportunities(
        self,
        days_ahead: int = 30,
        modalidades: Optional[List[int]] = None,
        max_pages_per_mod: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Busca contratações ativas, aplicando triagem temática, selo logístico e priorização."""
        today = date.today()
        dt_final = (today + timedelta(days=days_ahead)).strftime("%Y%m%d")
        modalidades = modalidades or [6, 4, 8, 12]

        total_scanned = 0
        total_matches = 0
        total_items = 0
        opportunities: List[Dict[str, Any]] = []

        logger.info(f"Buscando oportunidades ativas com prazo até {dt_final}...")

        for mod_id in modalidades:
            pagina = 1
            while True:
                resp = self.client.get_propostas_abertas(
                    data_final=dt_final,
                    codigo_modalidade=mod_id,
                    pagina=pagina,
                    tamanho_pagina=50,
                )

                if not resp:
                    break

                data_list = resp.get("data") or []
                if not data_list:
                    break

                for item in data_list:
                    total_scanned += 1
                    objeto = item.get("objetoCompra") or ""
                    info = item.get("informacaoComplementar") or ""

                    is_match, cat_name, sub_name, terms = self.matcher.match(objeto, info)
                    if is_match:
                        total_matches += 1

                        n_itens, downloaded_pdfs, briefing_path = self._process_matched_edital(item, cat_name, sub_name, terms)
                        total_items += n_itens

                        unidade = item.get("unidadeOrgao") or {}
                        geo_info = self.geo.match_localidade(unidade.get("municipioNome"), unidade.get("ufSigla"), objeto_texto=objeto)

                        opportunities.append({
                            "id": item.get("numeroControlePNCP"),
                            "title": objeto[:230],
                            "end_date": str(item.get("dataEncerramentoProposta") or "Ver Edital")[:10],
                            "file_paths": downloaded_pdfs,
                            "briefing_path": briefing_path,
                            "source": "PNCP",
                            "url": item.get("linkSistemaOrigem") or f"https://pncp.gov.br/app/editais/{item.get('numeroControlePNCP')}",
                            "geo_info": geo_info,
                            "is_priority_geo": geo_info.get("is_priority_geo", False),
                            "geo_distancia": geo_info.get("distancia_km") if geo_info.get("distancia_km") is not None else 999,
                            "valor_estimado": item.get("valorTotalEstimado") or 0.0,
                        })

                total_paginas = resp.get("totalPaginas") or 1
                paginas_restantes = resp.get("paginasRestantes") or 0

                if pagina % 5 == 0 or paginas_restantes <= 0:
                    logger.info(f"   Modalidade {mod_id} - Pág {pagina}/{total_paginas} (Restantes: {paginas_restantes}) | Total matches: {total_matches}")

                if (max_pages_per_mod and pagina >= max_pages_per_mod) or pagina >= total_paginas or paginas_restantes <= 0:
                    break

                pagina += 1

        # Ordena a fila priorizando as 7 bases operacionais e menores distâncias
        opportunities.sort(key=lambda x: (not x.get("is_priority_geo", False), x.get("geo_distancia", 999)))

        logger.info(f"Varredura concluída: {total_scanned} analisados | {total_matches} editais | {total_items} itens salvos.")
        return opportunities
