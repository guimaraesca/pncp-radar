"""
I.C.A.R.O. — Motor Genérico de Consumo da Gupy via __NEXT_DATA__
==================================================================
Estratégia de extração:
  1. GET https://{subdomain}.gupy.io/ -> parse __NEXT_DATA__ -> lista de vagas
  2. Para cada vaga nova: GET /jobs/{id} -> parse __NEXT_DATA__ -> detalhe completo
  3. Salva detalhe como .txt para análise pelo Gemini

Contrato de saída (lista de dicts):
  {
    "id": str,           # "{subdomain}_{job_id}"
    "title": str,        # "[LABEL] Título da Vaga"
    "end_date": str,     # Data limite ou "Não informado"
    "file_paths": list,  # [caminho_do_txt_salvo]
    "source": str,       # Label legível
    "url": str           # Link direto da vaga
  }
"""

import os
import re
import time
import json
import requests
from core.filter_utils import is_date_expired


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

REQUEST_TIMEOUT = 15
INTER_SUBDOMAIN_DELAY = 2
INTER_JOB_DELAY = 1
MAX_RETRIES = 2


def _get_session():
    """Cria uma Session com cookies persistentes para evitar bloqueio da Gupy."""
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _extract_next_data(html):
    """Extrai e parseia o JSON de __NEXT_DATA__ do HTML."""
    marker = "__NEXT_DATA__"
    if marker not in html:
        return None
    try:
        start = html.index(marker)
        json_start = html.index("{", start)
        json_end = html.index("</script>", json_start)
        return json.loads(html[json_start:json_end])
    except (ValueError, json.JSONDecodeError):
        return None


def _strip_html(text):
    """Remove tags HTML de um texto, mantendo o conteúdo."""
    if not text:
        return ""
    clean = re.sub(r"<br\s*/?>", "\n", text)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = re.sub(r"&nbsp;", " ", clean)
    clean = re.sub(r"&amp;", "&", clean)
    clean = re.sub(r"&lt;", "<", clean)
    clean = re.sub(r"&gt;", ">", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def _fetch_job_listing(subdomain, session):
    """Busca todas as vagas da home page de um subdomínio Gupy."""
    url = f"https://{subdomain}.gupy.io/"

    for attempt in range(MAX_RETRIES + 1):
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code != 200:
                if attempt < MAX_RETRIES:
                    time.sleep(3)
                    continue
                print(f"    [Gupy] {subdomain} retornou HTTP {r.status_code}")
                return [], ""

            nd = _extract_next_data(r.text)
            if not nd:
                if attempt < MAX_RETRIES:
                    time.sleep(3)
                    continue
                print(f"    [Gupy] {subdomain}: __NEXT_DATA__ não encontrado")
                return [], ""

            pp = nd.get("props", {}).get("pageProps", {})
            jobs = pp.get("jobs", [])
            company_name = pp.get("careerPage", {}).get("name", subdomain)
            return jobs, company_name

        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES:
                time.sleep(3)
                continue
            print(f"    [Gupy] Timeout ao acessar {subdomain}")
            return [], ""
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(3)
                continue
            print(f"    [Gupy] Erro ao acessar {subdomain}: {e}")
            return [], ""

    return [], ""


def _fetch_job_detail(subdomain, job_id, session):
    """Busca o detalhe completo de uma vaga via /jobs/{id}."""
    url = f"https://{subdomain}.gupy.io/jobs/{job_id}"
    try:
        r = session.get(url, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            return None

        nd = _extract_next_data(r.text)
        if not nd:
            return None

        pp = nd.get("props", {}).get("pageProps", {})
        return pp.get("job", None)

    except Exception:
        return None


def _matches_keywords(text, keywords):
    """Verifica se o texto contém ao menos uma palavra-chave."""
    if not keywords:
        return True
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def _matches_negative(text, negative_keywords):
    """Verifica se o texto contém alguma palavra-chave negativa."""
    if not negative_keywords:
        return False
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in negative_keywords)


def _save_job_as_txt(job_detail, job_listing, download_dir, unique_id, subdomain):
    """Salva o detalhe da vaga como .txt para análise pelo Gemini."""
    file_path = os.path.join(download_dir, f"{unique_id}.txt")

    lines = []

    if job_detail:
        lines.append(f"TITULO: {job_detail.get('name', 'N/A')}")
        lines.append(f"TIPO: {job_detail.get('jobType', 'N/A')}")

        city = job_detail.get("addressCity", "")
        state = job_detail.get("addressStateShortName", "")
        wtype = job_detail.get("workplaceType", "")
        lines.append(f"LOCAL: {city}, {state}")
        lines.append(f"MODALIDADE: {wtype}")

        lines.append(f"PUBLICADO: {job_detail.get('publishedAt', 'N/A')}")
        lines.append(f"PRAZO: {job_detail.get('expiresAt', job_detail.get('registerEndDate', 'Nao informado'))}")
        lines.append(f"URL: https://{subdomain}.gupy.io/jobs/{job_detail.get('id', '')}")
        lines.append("")

        desc = _strip_html(job_detail.get("description", ""))
        if desc:
            lines.append("DESCRICAO:")
            lines.append(desc)
            lines.append("")

        prereqs = _strip_html(job_detail.get("prerequisites", ""))
        if prereqs:
            lines.append("PRE-REQUISITOS:")
            lines.append(prereqs)
            lines.append("")

        responsibilities = _strip_html(job_detail.get("responsibilities", ""))
        if responsibilities:
            lines.append("RESPONSABILIDADES:")
            lines.append(responsibilities)
            lines.append("")

        relevant = _strip_html(job_detail.get("relevantExperiences", ""))
        if relevant:
            lines.append("EXPERIENCIA E BENEFICIOS:")
            lines.append(relevant)
    else:
        # Fallback: usa dados mínimos do listing
        title = job_listing.get("title", "N/A")
        lines.append(f"TITULO: {title}")

        wp = job_listing.get("workplace", {})
        addr = wp.get("address", {})
        lines.append(f"LOCAL: {addr.get('city', '?')}, {addr.get('stateShortName', '?')}")
        lines.append(f"MODALIDADE: {wp.get('workplaceType', '?')}")
        lines.append(f"DEPARTAMENTO: {job_listing.get('department', 'N/A')}")
        lines.append(f"TIPO: {job_listing.get('type', 'N/A')}")

    content = "\n".join(lines)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return file_path


def get_gupy_opportunities(
    subdomains,
    keywords,
    negative_keywords,
    download_dir,
    processed_ids,
    source_label,
):
    """
    Motor principal: itera sobre subdomínios Gupy, filtra por keywords,
    baixa detalhes e retorna oportunidades no formato I.C.A.R.O.
    """
    os.makedirs(download_dir, exist_ok=True)
    all_opportunities = []
    session = _get_session()

    for entry in subdomains:
        subdomain = entry["subdomain"]
        label = entry.get("label", subdomain)

        print(f"  [Gupy] Consultando {label} ({subdomain}.gupy.io)...")

        jobs, company_name = _fetch_job_listing(subdomain, session)

        if not jobs:
            print(f"    Nenhuma vaga aberta em {label}")
            time.sleep(INTER_SUBDOMAIN_DELAY)
            continue

        print(f"    {len(jobs)} vagas encontradas em {label}")

        for job in jobs:
            job_id = job.get("id")
            if not job_id:
                continue

            unique_id = f"{subdomain}_{job_id}"

            if unique_id in processed_ids:
                continue

            title = job.get("title", "")
            dept = job.get("department", "")
            searchable = f"{title} {dept}"

            # Filtro negativo
            if _matches_negative(searchable, negative_keywords):
                continue

            # Filtro positivo (se keywords vazia, aceita tudo)
            if keywords and not _matches_keywords(searchable, keywords):
                continue

            # Busca detalhe completo
            detail = _fetch_job_detail(subdomain, job_id, session)
            time.sleep(INTER_JOB_DELAY)

            # Se detalhe disponível, refazer filtro com texto completo
            if detail:
                full_text = " ".join([
                    title,
                    _strip_html(detail.get("description", "")),
                    _strip_html(detail.get("prerequisites", "")),
                    _strip_html(detail.get("responsibilities", "")),
                ])
                if _matches_negative(full_text, negative_keywords):
                    continue

            # Salva como .txt
            file_path = _save_job_as_txt(detail, job, download_dir, unique_id, subdomain)

            # Deadline
            deadline = "Não informado"
            if detail:
                deadline = detail.get("expiresAt", detail.get("registerEndDate", "Não informado"))
            if not deadline:
                deadline = "Não informado"

            # Descarta vagas com prazo já encerrado
            if is_date_expired(str(deadline)):
                processed_ids.add(unique_id)
                continue

            job_url = f"https://{subdomain}.gupy.io/jobs/{job_id}"

            opportunity = {
                "id": unique_id,
                "title": f"[{label}] {title}",
                "end_date": str(deadline),
                "file_paths": [file_path],
                "source": label,
                "url": job_url,
            }
            all_opportunities.append(opportunity)

        time.sleep(INTER_SUBDOMAIN_DELAY)

    print(f"  [Gupy] Total de novas oportunidades ({source_label}): {len(all_opportunities)}")
    return all_opportunities
