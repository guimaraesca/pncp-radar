import os
import json
import requests
from core.geo_utils import check_geo_requirements

# Queries expandidas (Eixos: EduMonitor/IDEB, Potiedu/Plataforma, BNCC Computação, ENEM e Formação)
QUERIES = [
    # --- Eixo EduMonitor: Inteligência, IDEB, SAEB e Metas (Prioridade Estratégica) ---
    "ideb",
    "saeb",
    "simulador ideb",
    "meta ideb",
    "copiloto educacional",
    "radar educacional",
    "avaliacao educacional",
    "avaliacao diagnostica",
    "avaliacao somativa",
    "avaliacao formativa",
    "sistema municipal de avaliacao",
    "sistema de avaliacao",
    "diagnostico educacional",
    "diagnostico de rede",
    "diagnostico escolar",
    "recomposicao de aprendizagem",
    "recuperacao de aprendizagem",
    "painel educacional",
    "dashboard educacional",
    "sala de situacao educacao",
    "sala de situacao",
    "indicadores educacionais",
    "evidencias educacionais",
    "gestao baseada em evidencias",
    "inteligencia educacional",
    "censo escolar",
    "learning analytics",
    "microdados educacionais",

    # --- Eixo Fluxo, Permanência e Evasão ---
    "distorcao idade serie",
    "abandono escolar",
    "evasao escolar",
    "busca ativa escolar",
    "correcao de fluxo",
    "fluxo escolar",

    # --- Eixo ENEM (Janela Temporal Urgente) ---
    "enem",
    "simulado enem",
    "plataforma enem",
    "preparatorio enem",

    # --- Eixo Potiedu: Plataforma, Software e Recursos Digitais ---
    "plataforma educacional",
    "plataforma educacional digital",
    "solucao educacional digital",
    "solucoes educacionais integradas",
    "licenca de uso de plataforma",
    "ambiente virtual de aprendizagem",
    "software educacional",
    "recurso educacional digital",
    "conteudo educacional digital",
    "educacao digital",
    "tecnologia educacional",
    "sistemas educacionais",

    # --- Eixo BNCC Computação, Robótica e STEAM ---
    "bncc computacao",
    "computacao na educacao basica",
    "pensamento computacional",
    "cultura digital",
    "letramento digital",
    "letramento computacional",
    "educacao midiatica",
    "robotica",
    "robotica educacional",
    "kit de robotica",
    "programacao",
    "steam",

    # --- Eixo Formação Continuada de Professores ---
    "formacao de professores",
    "formacao continuada",
    "formacao continuada de professores",
    "capacitacao de professores",
    "formacao docente",
    "itinerarios formativos",
    "trilha formativa",

    # --- Eixo Consultoria, Governança e Planos ---
    "consultoria educacao",
    "consultoria dados",
    "consultoria tecnologia",
    "consultoria governanca",
    "consultoria processos",
    "consultoria gestao de projetos",
    "consultoria transformacao digital",
    "servico tecnico educacao",
    "servico tecnico dados",
    "cientista de dados",
    "analista de dados",
    "gestao educacional",
    "politicas publicas educacionais",
    "plano municipal de educacao",
    "plano de educacao",
    "plano decenal de educacao",
    "plano nacional de educacao",
    "monitoramento plano de educacao",
    "referencial curricular",

    # --- Eixo Monitoramento & Avaliação (M&A) e Ciclos de Gestão de Políticas Públicas ---
    "monitoramento e avaliacao",
    "avaliacao de politicas publicas",
    "monitoramento de politicas publicas",
    "avaliacao de impacto",
    "avaliacao de resultados",
    "avaliacao de processos",
    "avaliacao ex-ante",
    "avaliacao ex-post",
    "plano plurianual",
    "ppa",
    "planejamento governamental",
    "gestao para resultados",
    "gpr",
    "indicadores de desempenho",
    "indicadores de resultado",
    "sala de situacao",
    "painel de monitoramento",
    "modernizacao da gestao publica",
    "desenho de programas publicos"
]

# Exclusões client-side (para evitar gastar IA com materiais físicos e compras genéricas)
NEGATIVOS = [
    "merenda",
    "alimentacao escolar",
    "transporte escolar",
    "obra",
    "reforma",
    "construcao",
    "mobiliario",
    "material de expediente",
    "uniforme",
    "limpeza",
    "vigilancia",
    "hospitalar",
    "combustivel",
    "veiculo",
    "locacao de veiculo"
]

def is_negative_match(text):
    if not text:
        return False
    text_lower = text.lower()
    for neg in NEGATIVOS:
        if neg in text_lower:
            return True
    return False

def get_new_opportunities(download_dir, processed_ids):
    os.makedirs(download_dir, exist_ok=True)
    opportunities = []
    seen_in_run = set()
    MAX_TOTAL_PNCP = 80  # Limite global expandido
    MAX_PER_QUERY = 2    # Garante diversidade temática em todas as 107 queries
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*'
    }

    for query in QUERIES:
        if len(opportunities) >= MAX_TOTAL_PNCP:
            break

        query_added = 0
        for tipo_doc in ["edital", "aviso", "contratacao"]:
            if query_added >= MAX_PER_QUERY:
                break
            try:
                url = f"https://pncp.gov.br/api/search/?q={query.replace(' ', '+')}&status=recebendo_proposta&tipos_documento={tipo_doc}&pagina=1&tam_pagina=6&ordenacao=-data"
                response = requests.get(url, headers=headers, timeout=20)
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", []) or data.get("data", []) or []
                    
                    for item in items:
                        if query_added >= MAX_PER_QUERY or len(opportunities) >= MAX_TOTAL_PNCP:
                            break
                            
                        # Extrai ID único do PNCP
                        numero_controle = item.get("numeroControlePNCP") or item.get("numero_controle") or item.get("id") or str(item.get("id_contratacao", ""))
                        if not numero_controle:
                            continue
                        
                        opp_id = str(numero_controle).replace("/", "_").replace("-", "_")
                        if opp_id in processed_ids or opp_id in seen_in_run:
                            continue
                        
                        # Extração do objeto real da licitação (na API search, o objeto está em 'description')
                        objeto = item.get("description") or item.get("objetoCompra") or item.get("objeto") or item.get("informacaoComplementar") or item.get("title") or "Objeto não informado"
                        edital_num = item.get("title") or item.get("numero") or ""
                        
                        # Filtro negativo client-side (descarta itens de merenda, obra, limpeza etc.)
                        if is_negative_match(objeto) or is_negative_match(item.get("informacaoComplementar", "")) or is_negative_match(edital_num):
                            continue
                            
                        seen_in_run.add(opp_id)
                        
                        # Órgão e Localidade (UF)
                        orgao_info = item.get("orgaoEntidade") or {}
                        orgao_nome = item.get("orgao_nome")
                        if not orgao_nome:
                            if isinstance(orgao_info, dict):
                                orgao_nome = orgao_info.get("razaoSocial") or orgao_info.get("nomeOrgao")
                            else:
                                orgao_nome = str(orgao_info)
                        orgao = orgao_nome or "Órgão Público"
                        uf = item.get("uf") or ""
                        orgao_local = f"{orgao}/{uf}" if uf else orgao
                            
                        # Modalidade
                        modalidade = item.get("modalidade_licitacao_nome") or item.get("modalidadeNome") or item.get("modalidade_nome") or "Licitação"
                        
                        # Título limpo e informativo
                        resumo_objeto = objeto.replace("\n", " ").strip()
                        if len(resumo_objeto) > 130:
                            resumo_objeto = resumo_objeto[:127] + "..."
                            
                        # Avaliação de conformidade com as 7 bases operacionais e raio 200km
                        geo_info = check_geo_requirements(f"{orgao_local} {objeto}", uf_hint=uf)
                        geo_badge = f"{geo_info['badge']} " if geo_info.get("badge") else ""
                        full_title = f"{geo_badge}[PNCP - {modalidade}] {orgao_local}: {resumo_objeto}"
                        
                        # Link direto e funcional para a oportunidade no Portal PNCP
                        numero_controle_limpo = item.get("numeroControlePNCP") or ""
                        cnpj_orgao = item.get("cnpj") or (orgao_info.get("cnpj") if isinstance(orgao_info, dict) else "")
                        ano_compra = item.get("anoCompra") or ""
                        seq_compra = item.get("numeroSequencial") or item.get("sequencialCompra") or ""

                        # Se tiver os parâmetros de órgão/compra, constrói URL estruturada
                        if cnpj_orgao and ano_compra and seq_compra:
                            link = f"https://pncp.gov.br/app/editais/{cnpj_orgao}/{ano_compra}/{seq_compra}"
                        elif numero_controle_limpo:
                            link = f"https://pncp.gov.br/app/editais/{numero_controle_limpo}"
                        else:
                            raw_link = item.get("link") or item.get("item_url") or ""
                            if raw_link.startswith("/compras/"):
                                path_parts = raw_link.replace("/compras/", "").strip("/").split("/")
                                link = f"https://pncp.gov.br/app/editais/{'/'.join(path_parts)}"
                            elif raw_link.startswith("http"):
                                link = raw_link.replace("pncp.gov.br/compras/", "pncp.gov.br/app/editais/")
                            else:
                                link = f"https://pncp.gov.br/app/editais?q={query.replace(' ', '+')}"

                        # Define o caminho do arquivo txt com os dados da oportunidade
                        file_path = os.path.join(download_dir, f"pncp_{opp_id}.txt")

                        # Tenta obter e baixar anexos/documentos oficiais (PDF do Edital/TR) diretamente da API de arquivos
                        doc_links = []
                        downloaded_files = [file_path]
                        
                        if cnpj_orgao and ano_compra and seq_compra:
                            try:
                                arq_url = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj_orgao}/compras/{ano_compra}/{seq_compra}/arquivos"
                                r_arq = requests.get(arq_url, headers=headers, timeout=8)
                                if r_arq.status_code == 200:
                                    arquivos = r_arq.json() or []
                                    for arq in arquivos:
                                        seq_arq = arq.get("sequencialDocumento") or arq.get("sequencial")
                                        titulo_arq = arq.get("titulo") or arq.get("tipoDocumentoNome") or "Documento"
                                        if seq_arq:
                                            download_url = f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj_orgao}/compras/{ano_compra}/{seq_compra}/arquivos/{seq_arq}"
                                            doc_links.append(f"{titulo_arq}: {download_url}")
                                            
                                            # Baixa o PDF oficial do Edital/TR via API
                                            try:
                                                r_doc = requests.get(download_url, headers=headers, timeout=15)
                                                if r_doc.status_code == 200 and len(r_doc.content) > 500:
                                                    pdf_filename = f"{opp_id}_doc_{seq_arq}.pdf"
                                                    pdf_dest = os.path.join(download_dir, pdf_filename)
                                                    with open(pdf_dest, "wb") as f_pdf:
                                                        f_pdf.write(r_doc.content)
                                                    downloaded_files.append(pdf_dest)
                                            except Exception:
                                                pass
                            except Exception:
                                pass

                        # Data limite e valor
                        data_fim = item.get("dataFimRecebimentoProposta") or item.get("dataAberturaProposta") or item.get("data_encerramento") or "Ver Edital"
                        valor = item.get("valorTotalEstimado") or item.get("valorEstimado") or item.get("valorGlobal") or "Não informado"
                        if isinstance(valor, (int, float)) and valor > 0:
                            valor = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        
                        # Salva arquivo formatado para leitura da IA
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(f"PORTAL: PNCP (Portal Nacional de Contratações Públicas)\n")
                            f.write(f"ÓRGÃO CONTRATANTE: {orgao_local}\n")
                            f.write(f"MODALIDADE: {modalidade}\n")
                            f.write(f"OBJETO DA CONTRATAÇÃO: {objeto}\n")
                            f.write(f"VALOR ESTIMADO: {valor}\n")
                            f.write(f"PRAZO PARA PROPOSTAS: {data_fim}\n")
                            f.write(f"LINK OFICIAL: {link}\n")
                            if geo_info.get("matched"):
                                f.write(f"BASE LOGÍSTICA COMPATÍVEL: {geo_info.get('base')} ({geo_info.get('tier')})\n")
                            if doc_links:
                                f.write("ARQUIVOS / ANEXOS OFICIAIS:\n" + "\n".join(doc_links) + "\n")
                            f.write("\nDADOS COMPLETOS EM JSON:\n")
                            f.write(json.dumps(item, indent=2, ensure_ascii=False))
                        
                        opportunities.append({
                            "id": opp_id,
                            "title": full_title[:230],
                            "end_date": str(data_fim)[:10] if data_fim != "Ver Edital" else "Ver Edital",
                            "file_paths": downloaded_files,
                            "source": "PNCP",
                            "url": link,
                            "geo_info": geo_info,
                            "is_priority_geo": geo_info.get("matched", False),
                            "geo_distancia": geo_info.get("distancia_km") if geo_info.get("distancia_km") is not None else 999
                        })
                    if items:
                        break # Se encontrou itens com o tipo_doc, passa para a próxima query
                else:
                    pass
            except Exception as e:
                print(f"Erro na requisição PNCP ({query} / {tipo_doc}): {e}")
                
    # Prioriza na fila de análise as oportunidades situadas nas 7 bases ou raio <= 200km
    opportunities.sort(key=lambda x: (not x.get("is_priority_geo", False), x.get("geo_distancia", 999)))
    return opportunities
