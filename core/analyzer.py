import os
import time
import requests
import json
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

CANDIDATE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

def analyze_opportunity(edital_text, linkedin_text):
    """
    Analyzes the edital text against the candidate's profile using Google Gemini REST API.
    Implements multi-model fallback across high-availability active Gemini models.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        api_key = api_key.strip()
    if not api_key or api_key == "sua_chave_gemini_aqui":
        return {
            "score": "Indefinido",
            "reasoning": "Chave da API do Gemini nao configurada no arquivo .env."
        }

    prompt = f"""
Voce e um especialista em recrutamento executivo e triagem de editais/oportunidades publicas, produtos educacionais e consultoria governamental.
Sua tarefa e analisar o edital, extrair as informacoes essenciais da vaga de forma estruturada e avaliar o alinhamento com a estrategia e perfil do candidato.

DIRETRIZES DE PONTUACAO / PESOS:
- TEMAS-ALVO (Prioridade Maxima para Score "Alta"):
  1. Copiloto IDEB, simulador de metas do IDEB/SAEB, sistemas municipais de avaliacao (diagnostica, formativa, somativa).
  2. Diagnostico educacional de rede, recomposicao e recuperacao de aprendizagem, gestao baseada em evidencias.
  3. Paineis/dashboards educacionais, sala de situacao, combate a evasao/abandono escolar, correcao de fluxo e distorcao idade-serie.
  4. Plataformas e simulados preparatorios para o ENEM.
  5. Plataforma educacional digital (SaaS), ambientes virtuais (AVA), licencas de software educacional.
  6. BNCC Computacao, Pensamento Computacional, Letramento/Cultura Digital, Robotica Educacional, Kits STEAM.
  7. Formacao Continuada de Professores em tecnologia, dados e inovacao curricular.
- TEMAS ADJACENTES (Score "Alta" ou "Media"): Planos Municipais/Estaduais de Educacao, Consultoria em Governanca Educacional, Avaliacao de Politicas Publicas, Engenharia/Analise de Dados Publicos.
- FORA DO ESCOPO (Score "Baixa"): Obras civis, reformas, alimentacao/merenda escolar, transporte escolar, compras de materiais genericos (expediente, limpeza, vigilancia, hospitalar).

DIRETRIZ GEOGRAFICA E LOGISTICA:
- Bases estrategicas da empresa: Sao Paulo (SP), Campinas (SP), Brasilia (DF), Goiania (GO), Joinville (SC), Recife (PE) e Natal (RN), raio de ate 200 km dessas bases, ou contratos 100% Remotos.
- Oportunidades com atuacao remota ou sediadas nestas regioes possuem viabilidade maxima.
- Exigencias presenciais em cidades fora desse raio (especialmente Norte ou regioes remotas) devem conter alerta explicito na justificativa.

PERFIL DO CANDIDATO:
{linkedin_text}

TEXTO DO EDITAL / TERMO DE REFERENCIA:
{edital_text[:25000]}

Extraia os dados da oportunidade e avalie a aderencia. Responda APENAS com um formato JSON valido contendo exatamente as chaves abaixo:
- "cargo": Titulo especifico da posicao, consultoria ou objeto contratado.
- "objeto": Breve resumo (1 a 2 linhas) do objetivo principal, escopo ou produtos a serem entregues.
- "requisitos": Requisitos obrigatorios e diferenciais essenciais exigidos (formacao academica, experiencia, competencias).
- "local": Local de atuacao e modalidade de trabalho (ex: Remoto, Hibrido - Brasilia/DF, Presencial - Cidade/UF).
- "contrato": Modalidade de contratacao e vigencia/duracao (ex: Consultoria por Produto - 150 dias, Licenca de Software, CLT).
- "valor": Valor global, valor por produto ou remuneracao (se nao constar no edital, responda "Nao informado").
- "prazo": Data limite exata para envio de propostas/inscricao (se nao constar, responda "Nao informado").
- "score": Grau de alinhamento do candidato ("Alta", "Media" ou "Baixa").
- "reasoning": Sintese de aderencia ULTRA-CONCISA (apenas 1 a 2 frases). Destaque a compatibilidade com os diferenciais (EduMonitor/IDEB/Potiedu/BNCC Computacao/Dados) e aponte alertas se houver (ex: local presencial fora da base), SEM reescrever o curriculo.
"""

    payload = {
      "contents": [{
        "parts":[{"text": prompt}]
      }],
      "generationConfig": {
        "responseMimeType": "application/json"
      }
    }
    headers = {'Content-Type': 'application/json'}

    for round_attempt in range(2):
        for model_name in CANDIDATE_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            raw_text = parts[0]["text"]
                            result = json.loads(raw_text)
                            return result

                elif response.status_code in [429, 503]:
                    print(f"Modelo {model_name} indisponivel temporariamente ({response.status_code}). Alternando...")
                    continue
                elif response.status_code in [400, 401, 403]:
                    print(f"Aviso Gemini ({response.status_code}): Chave sem permissao ou invalida. Pulando analise por IA.")
                    return {"score": "Indefinido", "reasoning": "Chave Gemini nao autenticada."}
                elif response.status_code == 404:
                    continue
                else:
                    print(f"Erro da API Gemini ({model_name}, Status {response.status_code}): {response.text[:150]}")
                    continue

            except Exception as e:
                print(f"Excecao ao chamar modelo {model_name}: {e}")
                continue

        if round_attempt == 0:
            time.sleep(5)

    return {
        "score": "Erro",
        "reasoning": "Erro de cota ou conexao na API do Gemini em todos os modelos testados."
    }

if __name__ == "__main__":
    pass
