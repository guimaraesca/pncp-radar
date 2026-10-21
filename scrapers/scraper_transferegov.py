"""
I.C.A.R.O. — Scraper Transferegov.br (Chamamentos Públicos, Parcerias e Convênios)
====================================================================================
Utiliza a API REST pública oficial do Transferegov (MGI / Governo Federal) via PostgREST.
Endpoint:
  - Listagem de Programas: GET https://api-publica.transferegov.gestao.gov.br/parcerias/programa
Permite monitorar programas federais abertos para transferências voluntárias,
termos de fomento e colaboração (MROSC) na área de educação, tecnologia e capacitação.
"""

import os
import requests
from core.filter_utils import is_relevant_opportunity

BASE_URL = "https://api-publica.transferegov.gestao.gov.br/parcerias/programa"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

REQUEST_TIMEOUT = 30


def _save_programa_txt(programa_id, prog, download_dir):
    file_path = os.path.join(download_dir, f"transferegov_{programa_id}.txt")
    lines = []

    nm_programa = prog.get("nm_programa") or "Programa sem título"
    ente = prog.get("nm_ente_superior") or prog.get("sg_ente_superior") or "Governo Federal"
    repassador = prog.get("nm_ente_repassador") or prog.get("sg_ente_repassador") or "Não informado"
    codigo = prog.get("cd_programa") or str(programa_id)
    tipo_inst = prog.get("tp_instrumento") or prog.get("cd_tipo_instrumento") or "Chamamento / Parceria"
    prazo = (
        prog.get("dt_fim_beneficiario_espontaneo")
        or prog.get("dt_fim_beneficiario_emenda")
        or prog.get("dt_fim_beneficiario_especifico")
        or "Ver Edital"
    )
    valor = prog.get("nr_vlr_global") or "Não informado"
    if isinstance(valor, (int, float)) and valor > 0:
        valor = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    link_portal = f"https://transferegov.sistema.gov.br/portal/programa?id={programa_id}"

    lines.append(f"PORTAL: Transferegov.br (Governo Federal)")
    lines.append(f"PROGRAMA: {nm_programa}")
    lines.append(f"CODIGO PROGRAMA: {codigo}")
    lines.append(f"ORGAO SUPERIOR: {ente}")
    lines.append(f"ORGAO REPASSADOR: {repassador}")
    lines.append(f"TIPO DE INSTRUMENTO: {tipo_inst}")
    lines.append(f"VALOR GLOBAL: {valor}")
    lines.append(f"PRAZO PARA PROPOSTAS: {prazo}")
    lines.append(f"SITUACAO: {prog.get('situacao_programa', 'Disponibilizado')}")
    lines.append(f"LINK PORTAL: {link_portal}")
    lines.append("")

    ds_obj = prog.get("ds_objetivo") or ""
    if ds_obj:
        lines.append("OBJETIVO DO PROGRAMA:")
        lines.append(ds_obj)
        lines.append("")

    ds_prob = prog.get("ds_problema") or ""
    if ds_prob:
        lines.append("PROBLEMA A SER ENFRENTADO:")
        lines.append(ds_prob)
        lines.append("")

    ds_pub = prog.get("ds_publico_alvo") or ""
    if ds_pub:
        lines.append("PUBLICO-ALVO:")
        lines.append(ds_pub)
        lines.append("")

    ds_res = prog.get("ds_resultado_esperado") or ""
    if ds_res:
        lines.append("RESULTADOS ESPERADOS:")
        lines.append(ds_res)
        lines.append("")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return file_path


def get_new_opportunities(download_dir, processed_ids):
    """
    Contrato padrão I.C.A.R.O.
    Consulta programas abertos no Transferegov.br via API REST.
    """
    os.makedirs(download_dir, exist_ok=True)
    opportunities = []

    print("[Transferegov] Consultando programas abertos via API oficial...")

    # Consulta as páginas de programas com status 'Disponibilizado'
    for page in [1, 2]:
        params = {
            "situacao_programa": "Disponibilizado",
            "pagina": page,
            "tamanho_da_pagina": 20,
        }
        try:
            r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if r.status_code != 200:
                print(f"  [Transferegov] Erro ao consultar página {page}: HTTP {r.status_code}")
                break

            data = r.json().get("data", [])
            if not data:
                break

            for prog in data:
                prog_id = str(prog.get("id_programa"))
                if not prog_id or prog_id in processed_ids:
                    continue

                nm_programa = prog.get("nm_programa") or ""
                ds_obj = prog.get("ds_objetivo") or ""
                ente = prog.get("nm_ente_superior") or prog.get("sg_ente_superior") or ""

                # Filtro de relevância semântica
                searchable = f"{nm_programa} {ds_obj} {ente}"
                if not is_relevant_opportunity(searchable):
                    continue

                file_path = _save_programa_txt(prog_id, prog, download_dir)
                prazo = (
                    prog.get("dt_fim_beneficiario_espontaneo")
                    or prog.get("dt_fim_beneficiario_emenda")
                    or prog.get("dt_fim_beneficiario_especifico")
                    or "Ver Edital"
                )

                opportunities.append({
                    "id": prog_id,
                    "title": f"[Transferegov] {nm_programa[:120]} ({ente})",
                    "end_date": str(prazo)[:10],
                    "file_paths": [file_path],
                    "source": "Transferegov",
                    "url": f"https://transferegov.sistema.gov.br/portal/programa?id={prog_id}",
                })

        except Exception as e:
            print(f"  [Transferegov] Exceção ao acessar API: {e}")
            break

    print(f"  [Transferegov] Total de programas filtrados: {len(opportunities)}")
    return opportunities
