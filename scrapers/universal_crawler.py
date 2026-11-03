"""Crawler Universal Inteligente para Portais de Editais e Vagas (I.C.A.R.O.).

Capaz de extrair oportunidades, editais em PDF e páginas de processos seletivos
de qualquer portal web cadastrado em config/sources.yaml, utilizando renderização
automática com Playwright e BeautifulSoup com heurísticas multilíngues.
"""

import os
import re
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("UniversalCrawler")

# Termos de interesse para identificar chamadas de consultoria, TIC e educação
KEYWORDS_OPPORTUNITY = [
    "edital", "termo de referência", "termo de referencia", "tr ", "tr-", "tr_",
    "consultor", "consultoria", "chamada", "seleção", "selecao", "processo seletivo",
    "vaga", "oportunidade", "job", "vacancy", "consultant", "procurement",
    "contratação", "contratacao", "especialista", "analista", "pesquisador",
    "inscrições abertas", "inscricoes abertas", "manifestação de interesse",
]

# Padrões de regex para identificar datas limites
DATE_PATTERNS = [
    r"(?:até|ate|prazo|limite|encerramento|deadline|closing date)[\s\:\-]+(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4}(?:\s*(?:às|as)\s*\d{1,2}(?:\:\d{2})?)?)",
    r"(\d{1,2}\s+de\s+[a-zçA-ZÇ]+\s+de\s+\d{4})",
    r"(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{4})",
]


def extract_deadline_from_text(text: str) -> Optional[str]:
    """Tenta localizar no texto da página ou edital a data limite de inscrição."""
    if not text:
        return None
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            found = match.group(1).strip()
            # Validação simples para não pegar anos muito antigos
            if any(y in found for y in ["2026", "2027", "2028"]):
                return found
    return None


def fetch_with_playwright(url: str, wait_selector: Optional[str] = None) -> str:
    """Carrega páginas dinâmicas (SPA/JavaScript) via Playwright."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            })
            page.goto(url, wait_until="networkidle", timeout=25000)
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=5000)
                except Exception:
                    pass
            time.sleep(2)
            content = page.content()
            browser.close()
            return content
    except Exception as e:
        logger.warning(f"Playwright falhou para {url}: {e}. Tentando fallback HTTP.")
        return ""


def crawl_source_opportunities(
    source_info: Dict[str, Any],
    download_dir: str,
    processed_ids: Set[str],
    max_items: int = 8
) -> List[Dict[str, Any]]:
    """Varre um portal específico para encontrar novos editais, vagas e anexos em PDF."""
    source_id = source_info.get("id", "source")
    source_name = source_info.get("nome", source_id.upper())
    base_url = source_info.get("url", "")
    target_dir = Path(download_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    if not base_url:
        return []

    logger.info(f"🌐 [{source_name}] Conectando a {base_url}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    html_content = ""
    try:
        # Tentativa rápida via requests
        resp = requests.get(base_url, headers=headers, timeout=15)
        if resp.status_code == 200 and len(resp.text) > 2000:
            html_content = resp.text
    except Exception as e:
        logger.debug(f"Requests direto falhou para {base_url}: {e}")

    # Se a página for SPA (JavaScript), usa Playwright
    if not html_content or len(html_content) < 3000 or "<div id=\"root\"></div>" in html_content or "<app-root>" in html_content:
        html_content = fetch_with_playwright(base_url)

    if not html_content:
        logger.warning(f"⚠️ [{source_name}] Não foi possível obter o conteúdo da página.")
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    found_opps = []
    seen_urls = set()

    # 1. Procura por links que apontem para termos de referência, editais ou páginas de vagas
    all_links = soup.find_all("a", href=True)

    for a_tag in all_links:
        href = a_tag["href"].strip()
        link_text = a_tag.get_text().strip()
        full_url = urljoin(base_url, href)

        if full_url in seen_urls:
            continue

        # Verifica se o link ou o texto possui indicativos de oportunidade/edital
        combined_text = (link_text + " " + href).lower()
        is_relevant = any(k in combined_text for k in KEYWORDS_OPPORTUNITY) or href.lower().endswith(".pdf")

        if not is_relevant:
            continue

        # Filtra links genéricos (ex: "home", "sobre nós")
        if len(link_text) < 4 and not href.lower().endswith(".pdf"):
            continue

        item_id = f"{source_id}_{abs(hash(full_url)) % 1000000:06d}"
        if item_id in processed_ids:
            continue

        seen_urls.add(full_url)
        title = link_text if len(link_text) > 8 else a_tag.get("title") or a_tag.get("aria-label") or Path(urlparse(full_url).path).name
        title = " ".join(str(title).split())

        # Tenta extrair prazo do bloco pai ou do texto próximo
        parent_text = a_tag.parent.get_text() if a_tag.parent else ""
        prazo_detectado = extract_deadline_from_text(parent_text) or "Não informada"

        pdf_files = []
        # Se for um PDF direto, faz download
        if full_url.lower().endswith(".pdf") or "download" in full_url.lower():
            file_name = f"{item_id}.pdf"
            file_path = target_dir / file_name
            try:
                r = requests.get(full_url, headers=headers, timeout=20)
                if r.status_code == 200 and len(r.content) > 1024:
                    with open(file_path, "wb") as f:
                        f.write(r.content)
                    pdf_files.append(str(file_path))
            except Exception as e:
                logger.debug(f"Falha ao baixar PDF {full_url}: {e}")

        found_opps.append({
            "id": item_id,
            "title": f"[{source_name}] {title}",
            "end_date": prazo_detectado,
            "file_paths": pdf_files,
            "source": source_name,
            "url": full_url,
        })

        if len(found_opps) >= max_items:
            break

    logger.info(f"✅ [{source_name}] {len(found_opps)} novas oportunidades detectadas.")
    return found_opps
