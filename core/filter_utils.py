"""
I.C.A.R.O. — Utilitário de Filtros de Relevância, Prazos e Palavras-Chave
==========================================================================
Centraliza a lógica de pré-filtragem para:
1. Descartar vagas e itens operacionais fora de escopo (cozinha, limpeza, solda).
2. Descartar processos seletivos e editais de anos anteriores (ex: 2024, 2025).
3. Descartar vagas com prazos de inscrição já vencidos / expirados.
4. Descartar bancos de talentos genéricos sem vagas imediatas abertas.
"""

import os
import re
from datetime import datetime, date
import yaml

CURRENT_YEAR = datetime.now().year  # 2026

DEFAULT_KEYWORDS = [
    # Dados & Inteligência Artificial
    "inteligência artificial", "inteligencia artificial", "machine learning",
    "ciência de dados", "ciencia de dados", "análise de dados", "analise de dados",
    "business intelligence", "power bi", "dashboard", "dashboards", "painel de indicadores",
    "sala de situação", "sala de situacao", "interoperabilidade", "microdados educacionais",
    # Avaliação Educacional & Indicadores
    "saeb", "ideb", "enem", "simulados enem", "simulado enem", "indicadores educacionais",
    "avaliação diagnóstica", "avaliacao diagnostica", "avaliação formativa", "avaliacao da aprendizagem",
    "recomposição de aprendizagem", "recomposicao de aprendizagem", "fluência leitora",
    "fluencia leitora", "censo escolar", "fluxo escolar", "evasão", "evasao", "abandono escolar",
    "matriz de referência", "matriz de referencia", "diagnóstico de aprendizagem", "diagnostico pedagogico",
    # Educação Digital, STEAM & Robótica
    "pensamento computacional", "letramento computacional", "cultura digital",
    "competências digitais", "bncc", "bncc computação", "bncc computacao",
    "robótica educacional", "robotica educacional", "cultura maker", "gamificação", "gamificacao",
    "educação conectada", "educacao conectada", "inovação curricular", "inovacao curricular",
    # Sistemas Educacionais (EMIS / SIGE) & Educação Profissional
    "sistema de gestão escolar", "sistema de gestao escolar", "gestão educacional", "gestao educacional",
    "gestão escolar", "gestao escolar", "software de gestão escolar", "diário de classe digital",
    "sige", "emis", "gestão presente", "gestao presente", "educação profissional", "educacao profissional",
    "ensino técnico", "ensino tecnico", "itinerário formativo", "itinerarios formativos",
    # Materiais Didáticos & Soluções Educacionais
    "material didático", "material didatico", "materiais didáticos", "materiais didaticos",
    "material didático estruturado", "solução educacional", "solucao educacional",
    "plataforma educacional", "plataforma de aprendizagem", "ambiente virtual de aprendizagem", "ava",
    # Formação Docente & Políticas Públicas
    "formação de professores", "formacao de professores", "formação continuada", "formacao continuada",
    "capacitação docente", "capacitacao docente", "desenvolvimento profissional docente",
    "políticas públicas", "politicas publicas", "gestão pública", "gestao publica",
    "governança", "governanca", "governo digital", "transformação digital", "transformacao digital",
    "consultoria", "pedagógico", "pedagogico", "aprendizagem", "ensino",
    "tecnologia", "inovação", "inovacao", "digital",
    "analista", "especialista", "coordenador", "gerente", "diretor", "produto", "projetos",
    "docente", "professor", "instrutor", "pesquisa"
]

DEFAULT_NEGATIVE_KEYWORDS = [
    # Funções operacionais e manutenção
    "motorista", "porteiro", "zelador", "vigilante", "copeiro",
    "recepcionista", "auxiliar de limpeza", "servente", "jardineiro",
    "cozinheiro", "merendeira", "soldador", "caldeireiro", "eletricista",
    "mecanico", "mecânico", "pintor", "ajudante de cozinha", "manicure",
    "cabeleireiro", "garçom", "garcom", "atendente de lanchonete",
    "almoxarife", "estoquista", "operador de caldeira", "pedreiro",
    "carpinteiro", "serralheiro", "borracheiro", "lavador",
    
    # Saúde ocupacional, medicina do trabalho e enfermagem
    "medicina do trabalho", "seguranca do trabalho", "saúde ocupacional",
    "saude ocupacional", "tecnico em enfermagem", "enfermeiro", "auxiliar de farmacia",
    
    # Obras civis pesadas e pavimentação
    "asfalto", "pavimentação", "pavimentacao", "drenagem pluvial", "obras civis",
    
    # Etapas intermediárias e documentos de concurso
    "gabarito", "resultado final", "resultado da prova", "agenda de avaliacao",
    "agenda da avaliacao", "retificacao", "retificação", "convocação",
    "convocacao", "lista de aprovados",
    
    # Bancos de talentos genéricos sem contratação imediata
    "banco de talentos", "banco de currículos", "banco de curriculos",
    "cadastro de reserva", "cadastro reserva", "deixe seu currículo",
    "deixe seu curriculo", "deixe aqui seu currículo", "deixe aqui seu curriculo",
    "não encontrou uma vaga para você", "nao encontrou uma vaga para voce"
]


def load_filter_config():
    """Carrega listas do gupy_sources.yaml se existir, senão usa defaults."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        "gupy_sources.yaml"
    )
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                kw = data.get("keywords", DEFAULT_KEYWORDS)
                nkw = data.get("negative_keywords", DEFAULT_NEGATIVE_KEYWORDS)
                all_nkw = list(set(nkw + DEFAULT_NEGATIVE_KEYWORDS))
                return kw, all_nkw
        except Exception:
            pass
    return DEFAULT_KEYWORDS, DEFAULT_NEGATIVE_KEYWORDS


def is_past_year(text: str, current_year: int = CURRENT_YEAR) -> bool:
    """
    Retorna True se o texto/link indicar explicitamente um ano anterior ao vigente.
    Exemplos: '49/2024', '82-2025', '/2024/', 'estagio 2025'.
    """
    if not text:
        return False
    # Procura anos de 4 dígitos entre 2000 e 2099
    matches = re.findall(r"(?:^|[\D])(20\d{2})(?:$|[\D])", text)
    for m in matches:
        try:
            year = int(m)
            if 2010 <= year < current_year:
                return True
        except ValueError:
            continue
    return False


def is_date_expired(date_str: str) -> bool:
    """
    Avalia se uma data em formato texto (ISO, DD/MM/AAAA, etc.) já expirou em relação a hoje.
    Retorna False se a data não puder ser parseada (fail-safe).
    """
    if not date_str or not isinstance(date_str, str):
        return False
        
    s = date_str.strip().split("T")[0].split(" ")[0]  # Remove horário se houver
    today = date.today()
    
    # Formato ISO: YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
            return d < today
        except ValueError:
            pass
            
    # Formato BR: DD/MM/YYYY
    if re.match(r"^\d{2}/\d{2}/\d{4}$", s):
        try:
            d = datetime.strptime(s, "%d/%m/%Y").date()
            return d < today
        except ValueError:
            pass
            
    return False


def is_relevant_opportunity(title: str, description: str = "", date_str: str = "") -> bool:
    """
    Retorna True se a oportunidade for relevante e atual para o perfil do I.C.A.R.O.
    Descarta:
      - Termos operacionais negativos e bancos de talentos
      - Anos anteriores explícitos no título/texto (ex: 2024, 2025)
      - Prazos já vencidos
    """
    # 1. Verifica se a data limite já expirou
    if date_str and is_date_expired(date_str):
        return False

    # 2. Verifica se o título referencia processo antigo (ex: 2024/2025)
    if is_past_year(title):
        return False

    keywords, negative_keywords = load_filter_config()
    text = f"{title} {description}".lower()

    # 3. Filtro negativo estrito: descarta operacionais e bancos de talentos
    for nkw in negative_keywords:
        if nkw.lower() in text:
            return False

    # 4. Filtro positivo: deve conter ao menos uma palavra-chave
    for kw in keywords:
        if kw.lower() in text:
            return True

    return False
