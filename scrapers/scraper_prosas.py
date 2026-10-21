"""
I.C.A.R.O. — Scraper Prosas (Central de Editais e Financiamento Social)
========================================================================
Utiliza a API REST pública oficial do Prosas via OAuth2 (Client Credentials).
Endpoint:
  - Auth: POST https://prosas.com.br/auth/oauth2/token
  - Listagem: GET https://prosas.com.br/selecao/api/v2/third_party/oportunidades/inscricoes_abertas
  - Detalhe: GET https://prosas.com.br/selecao/api/v2/third_party/oportunidades/{id}
"""

import os
import re
import time
import requests
import yaml

PROSAS_CLIENT_ID = "lsf6jeu7-Wk04P2iSYMdcMhPZUNZqabK8CG6mAfRQ6M"
AUTH_URL = "https://prosas.com.br/auth/oauth2/token"
BASE_API = "https://prosas.com.br/selecao/api/v2/third_party/oportunidades"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

REQUEST_TIMEOUT = 15


def _load_keywords():
    """Carrega palavras-chave e termos negativos do YAML central."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        "gupy_sources.yaml",
    )
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            return cfg.get("keywords", []), cfg.get("negative_keywords", [])
    return [], []


def _strip_html(text):
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


def _get_access_token():
    """Obtém token Bearer via OAuth2 client_credentials."""
    payload = {
        "grant_type": "client_credentials",
        "client_id": PROSAS_CLIENT_ID,
        "scope": "public",
    }
    try:
        r = requests.post(AUTH_URL, json=payload, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            return r.json().get("access_token")
        print(f"  [Prosas] Erro ao obter token: HTTP {r.status_code}")
    except Exception as e:
        print(f"  [Prosas] Falha na autenticação OAuth2: {e}")
    return None


def _matches_keywords(text, keywords):
    if not keywords:
        return True
    tl = text.lower()
    return any(kw.lower() in tl for kw in keywords)


def _matches_negative(text, negative_keywords):
    if not negative_keywords:
        return False
    tl = text.lower()
    return any(nkw.lower() in tl for nkw in negative_keywords)


def _save_edital_txt(edital_id, attrs, detail_attrs, download_dir):
    file_path = os.path.join(download_dir, f"prosas_{edital_id}.txt")
    lines = []

    nome = attrs.get("nome") or detail_attrs.get("nome", "Sem título")
    empresa = attrs.get("nome_empresa") or detail_attrs.get("nome_empresa", "Não informada")
    prazo = attrs.get("encerramento_das_inscricoes") or detail_attrs.get("encerramento_das_inscricoes", "Não informado")
    valor = detail_attrs.get("valor_total_disponivel") or detail_attrs.get("valor_limite", "Não informado")
    link = detail_attrs.get("link") or f"https://prosas.com.br/editais/{edital_id}"

    lines.append(f"TITULO: {nome}")
    lines.append(f"ORGANIZACAO / PATROCINADOR: {empresa}")
    lines.append(f"PRAZO FINAL: {prazo}")
    lines.append(f"VALOR DISPONIVEL: {valor}")
    lines.append(f"URL: {link}")
    lines.append("")

    resumo = _strip_html(attrs.get("resumo") or "")
    if resumo:
        lines.append("RESUMO:")
        lines.append(resumo)
        lines.append("")

    descricao = _strip_html(detail_attrs.get("descricao") or "")
    if descricao:
        lines.append("DESCRICAO DO EDITAL:")
        lines.append(descricao)
        lines.append("")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return file_path


def get_new_opportunities(download_dir, processed_ids):
    """
    Contrato padrão I.C.A.R.O.
    Consulta editais abertos na plataforma Prosas via API REST.
    """
    print("[Prosas] Iniciando consulta via API oficial...")
    token = _get_access_token()
    if not token:
        print("  [Prosas] Não foi possível autenticar. Abortando busca.")
        return []

    keywords, negative_keywords = _load_keywords()
    auth_headers = {
        **HEADERS,
        "Authorization": f"Bearer {token}",
    }

    os.makedirs(download_dir, exist_ok=True)
    opportunities = []

    # Busca as duas primeiras páginas (40 editais mais recentes)
    for page in [1, 2]:
        list_url = f"{BASE_API}/inscricoes_abertas?include=area_interesses,incentivador&page[page]={page}&page[size]=20"
        try:
            r = requests.get(list_url, headers=auth_headers, timeout=REQUEST_TIMEOUT)
            if r.status_code != 200:
                print(f"  [Prosas] Erro ao listar página {page}: HTTP {r.status_code}")
                break

            data = r.json().get("data", [])
            if not data:
                break

            for item in data:
                edital_id = str(item.get("id"))
                if not edital_id or edital_id in processed_ids:
                    continue

                attrs = item.get("attributes", {})
                nome = attrs.get("nome", "")
                empresa = attrs.get("nome_empresa", "")
                searchable = f"{nome} {empresa}"

                # Filtro prévio por keywords
                if _matches_negative(searchable, negative_keywords):
                    continue
                if keywords and not _matches_keywords(searchable, keywords):
                    # Se não bater no título, tenta obter o detalhe para checar a descrição
                    pass

                # Busca detalhe completo do edital
                detail_url = f"{BASE_API}/{edital_id}"
                detail_attrs = {}
                try:
                    time.sleep(0.5)
                    r_det = requests.get(detail_url, headers=auth_headers, timeout=REQUEST_TIMEOUT)
                    if r_det.status_code == 200:
                        detail_attrs = r_det.json().get("data", {}).get("attributes", {})
                except Exception:
                    pass

                full_text = " ".join([
                    searchable,
                    _strip_html(detail_attrs.get("descricao", "")),
                    _strip_html(detail_attrs.get("resumo", "")),
                ])

                if _matches_negative(full_text, negative_keywords):
                    continue
                if keywords and not _matches_keywords(full_text, keywords):
                    continue

                file_path = _save_edital_txt(edital_id, attrs, detail_attrs, download_dir)
                prazo = attrs.get("encerramento_das_inscricoes") or detail_attrs.get("encerramento_das_inscricoes", "Não informado")
                url_edital = detail_attrs.get("link") or f"https://prosas.com.br/editais/{edital_id}"

                opportunities.append({
                    "id": edital_id,
                    "title": f"[Prosas] {nome}",
                    "end_date": str(prazo),
                    "file_paths": [file_path],
                    "source": "Prosas",
                    "url": url_edital,
                })

        except Exception as e:
            print(f"  [Prosas] Exceção durante requisição da página {page}: {e}")
            break

    print(f"  [Prosas] Total de oportunidades filtradas: {len(opportunities)}")
    return opportunities
