"""Módulo de NLP (Processamento de Linguagem Natural) e Análise Estratégica de Editais.

Oferece:
- Limpeza e tokenização de textos jurídicos e descrições de compras públicas.
- Remoção cirúrgica de stopwords em português e termos de boilerplate de licitações.
- Extração de N-Grams (unigramas, bigramas e trigramas mais frequentes).
- Modelagem e relevância via TF-IDF.
- Matriz de Valor Estratégico: Cruzamento de Frequência de Termos x Volume Financeiro (R$).
- Geração de Nuvem de Palavras (Word Cloud) ponderada por Frequência ou por Orçamento (R$).
- Classificação temática em clusters de oportunidades de alto valor.
"""

import io
import math
import re
import unicodedata
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

# Stopwords de Língua Portuguesa + Boilerplate de Licitações Públicas
STOPWORDS_PADRAO: Set[str] = {
    # Preposições, artigos, conjunções, pronomes
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "por", "pelo", "pela", "pelos", "pelas", "com",
    "sem", "sob", "sobre", "tras", "para", "pra", "pro", "ao", "aos", "aonde", "onde",
    "e", "ou", "mas", "porem", "contudo", "todavia", "entretanto", "que", "se", "como",
    "quando", "porque", "pois", "ja", "mais", "menos", "muito", "pouco", "bem", "mal",
    "seu", "sua", "seus", "suas", "meu", "minha", "nosso", "nossa", "este", "esta",
    "estes", "estas", "esse", "essa", "esses", "essas", "aquele", "aquela", "aqueles",
    "isto", "isso", "aquilo", "qual", "quais", "quem", "cujo", "cuja", "dele", "dela",
    "ele", "ela", "eles", "elas", "nos", "vos", "lhe", "lhes", "me", "te", "se",
    "ser", "estar", "ter", "haver", "sendo", "tendo", "havendo", "foi", "foram", "era",
    "sao", "tem", "ha", "pode", "podem", "deve", "devem",

    # Jargão e Boilerplate Governamental / Licitações (ruído que não diferencia estratégia)
    "contratacao", "contratação", "empresa", "empresas", "prestacao", "prestação",
    "servico", "serviço", "servicos", "serviços", "fornecimento", "aquisicao", "aquisição",
    "objeto", "edital", "anexo", "anexos", "termo", "termos", "referencia", "referência",
    "especificacao", "especificação", "especificacoes", "especificações", "conforme",
    "atraves", "através", "mediante", "fins", "atendimento", "necessidade", "necessidades",
    "secretaria", "secretarias", "prefeitura", "municipio", "município", "municipal",
    "municipais", "estadual", "estaduais", "federal", "federais", "governo", "orgao",
    "órgão", "orgaos", "órgãos", "instituto", "camara", "câmara", "fundo", "conselho",
    "item", "itens", "lote", "lotes", "valor", "estimado", "global", "total", "unidade",
    "unidades", "prazo", "meses", "dias", "ano", "anos", "vigencia", "vigência",
    "execucao", "execução", "licitacao", "licitação", "licitacoes", "licitações",
    "pregao", "pregão", "eletronico", "eletrônico", "registro", "precos", "preços",
    "gerenciamento", "apoio", "suporte", "continuada", "continuado", "eventual",
    "futura", "futuro", "atender", "visando", "destinado", "destinada", "destinados",
    "destinadas", "compreendendo", "compreende", "quantidades", "quantidade",
    "administracao", "administração", "publica", "pública", "publico", "público",
    "publicas", "públicas", "publicos", "públicos", "especializada", "especializadas",
    "especializado", "especializados", "tecnico", "técnico", "tecnica", "técnica",
    "tecnicos", "técnicos", "tecnicas", "técnicas", "ativos", "ativo", "forma",
    "meio", "meios", "tendo", "sendo", "havendo", "uso", "utilizacao", "utilização",
    "respectivo", "respectiva", "respectivos", "respectivas", "incluindo", "constantes",
    "detalhado", "detalhadas", "abaixo", "acima", "geral", "diversos", "diversas",
    "demais", "condicoes", "condições", "exigencias", "exigências", "estabelecidas",
    "estabelecido", "solucao", "solucoes", "solução", "soluções", "implantacao",
    "implantação", "equipamentos", "equipamento"
}


def normalizar_texto(texto: str, remover_acentos: bool = True) -> str:
    """Limpa e normaliza texto removendo pontuação, números e espaços duplicados."""
    if not texto or not isinstance(texto, str):
        return ""
    texto = texto.lower()
    if remover_acentos:
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(c for c in texto if not unicodedata.combining(c))
    # Remove URLs e links
    texto = re.sub(r"https?://\S+|www\.\S+", " ", texto)
    # Remove pontuações, dígitos e caracteres especiais, mantendo apenas letras e espaços
    texto = re.sub(r"[^a-zA-ZáéíóúâêîôûãõçÁÉÍÓÚÂÊÎÔÛÃÕÇ\s]", " ", texto)
    # Normaliza espaços
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


class NLPAnalytics:
    """Motor de análise semântica e NLP para o ecossistema de editais do PNCP."""

    def __init__(self, stopwords_adicionais: Optional[Set[str]] = None):
        self.stopwords = set(STOPWORDS_PADRAO)
        if stopwords_adicionais:
            self.stopwords.update({normalizar_texto(w) for w in stopwords_adicionais})

    def tokenizar(self, texto: str) -> List[str]:
        """Quebra texto em tokens filtrando stopwords e palavras muito curtas (< 3 caracteres)."""
        texto_limpo = normalizar_texto(texto)
        tokens = texto_limpo.split()
        return [t for t in tokens if len(t) > 2 and t not in self.stopwords]

    def extrair_ngrams(
        self,
        textos: List[str],
        n: int = 2,
        top_k: int = 30
    ) -> pd.DataFrame:
        """Extrai n-gramas (unigramas, bigramas ou trigramas) mais frequentes."""
        contador: Counter = Counter()

        for txt in textos:
            tokens = self.tokenizar(txt)
            if len(tokens) < n:
                continue
            for i in range(len(tokens) - n + 1):
                ngram = " ".join(tokens[i : i + n])
                contador[ngram] += 1

        df = pd.DataFrame(contador.most_common(top_k), columns=["termo", "frequencia"])
        df["tipo_ngram"] = f"{n}-grama"
        return df

    def extrair_matriz_estrategica(
        self,
        df: pd.DataFrame,
        campo_texto: str = "objeto_compra",
        campo_valor: str = "valor_total_estimado",
        top_k: int = 40,
        tipos_ngram: Tuple[int, ...] = (1, 2, 3)
    ) -> pd.DataFrame:
        """Cruza cada termo/n-grama com o impacto financeiro (R$) e alcance em editais."""
        if df.empty or campo_texto not in df.columns:
            return pd.DataFrame()

        # Coleta textos e valores
        registros = []
        for _, row in df.iterrows():
            txt = row.get(campo_texto) or ""
            val = row.get(campo_valor) or 0.0
            try:
                val = float(val) if val and not pd.isna(val) else 0.0
            except (ValueError, TypeError):
                val = 0.0
            registros.append((self.tokenizar(txt), val, row))

        # Agrega termos
        termo_dados: Dict[str, Dict[str, Any]] = {}

        for tokens, val, row in registros:
            termos_encontrados_neste_edital = set()

            for n in tipos_ngram:
                if len(tokens) < n:
                    continue
                for i in range(len(tokens) - n + 1):
                    ngram = " ".join(tokens[i : i + n])
                    termos_encontrados_neste_edital.add((ngram, f"{n}-grama"))

            for ngram, tipo in termos_encontrados_neste_edital:
                if ngram not in termo_dados:
                    termo_dados[ngram] = {
                        "termo": ngram,
                        "tipo_ngram": tipo,
                        "frequencia": 0,
                        "valor_total_estimado": 0.0,
                        "valores": [],
                        "orgaos": set(),
                        "ufs": set()
                    }
                termo_dados[ngram]["frequencia"] += 1
                termo_dados[ngram]["valor_total_estimado"] += val
                if val > 0:
                    termo_dados[ngram]["valores"].append(val)
                if row.get("razao_social_orgao"):
                    termo_dados[ngram]["orgaos"].add(str(row["razao_social_orgao"]))
                if row.get("uf_sigla"):
                    termo_dados[ngram]["ufs"].add(str(row["uf_sigla"]))

        if not termo_dados:
            return pd.DataFrame()

        linhas = []
        for ngram, d in termo_dados.items():
            freq = d["frequencia"]
            # Exige relevância mínima (aparecer em pelo menos 2 editais se for unigrama, ou 1 se for bigrama/trigrama de alto valor)
            if freq < 2 and d["tipo_ngram"] == "1-grama":
                continue

            v_tot = d["valor_total_estimado"]
            ticket_medio = (v_tot / freq) if freq > 0 else 0.0
            # Score estratégico combina frequência com log do volume financeiro
            score = freq * (math.log10(v_tot + 10) if v_tot > 0 else 1.0)

            linhas.append({
                "termo": ngram,
                "tipo_ngram": d["tipo_ngram"],
                "frequencia": freq,
                "valor_total_estimado": round(v_tot, 2),
                "ticket_medio": round(ticket_medio, 2),
                "total_orgaos": len(d["orgaos"]),
                "total_ufs": len(d["ufs"]),
                "score_estrategico": round(score, 2),
                "categoria_estrategica": self._categorizar_termo(ngram)
            })

        df_res = pd.DataFrame(linhas)
        if df_res.empty:
            return df_res

        df_res.sort_values(by=["score_estrategico", "valor_total_estimado"], ascending=False, inplace=True)
        df_res.reset_index(drop=True, inplace=True)
        return df_res.head(top_k)

    def _categorizar_termo(self, termo: str) -> str:
        """Classifica o termo em clusters de posicionamento estratégico."""
        t = termo.lower()
        if any(k in t for k in ["ideb", "saeb", "aprendizagem", "aluno", "escola", "educacao", "educacional", "pedagogico", "enem", "docente", "professor", "ensino", "letramento", "robotica", "steam", "computacional", "computacao", "maker", "bncc"]):
            return "Educação & Evidências (IDEB)"
        if any(k in t for k in ["monitoramento", "avaliacao", "impacto", "politicas", "ppa", "metas", "governamental", "indicadores", "sala situacao", "efetividade", "planejamento", "gpr"]):
            return "M&A e Políticas Públicas"
        if any(k in t for k in ["inteligencia artificial", "ia", "dados", "analytics", "business intelligence", "machine learning", "algoritmo", "ciencia"]):
            return "IA & Ciência de Dados"
        if any(k in t for k in ["plataforma", "software", "licenca", "nuvem", "cloud", "saas", "aplicativo", "sistema", "service", "web"]):
            return "Plataformas & Software (SaaS)"
        if any(k in t for k in ["seguranca", "ciberseguranca", "firewall", "redes", "infraestrutura", "datacenter", "data center", "servidor", "backup", "soc", "siem", "blade", "rack"]):
            return "Infraestrutura & Cibersegurança"
        if any(k in t for k in ["consultoria", "capacitacao", "treinamento", "processos", "governanca", "lideranca"]):
            return "Consultoria & Governança"
        if any(k in t for k in ["folha", "pagamento", "financeira", "banco", "pensionistas", "inativos", "saude"]):
            return "Gestão Administrativa & Apoio"
        return "Tecnologia & Inovação"

    def gerar_nuvem_palavras(
        self,
        frequencias_ou_df: Any,
        tipo_peso: str = "frequencia",
        largura: int = 900,
        altura: int = 450,
        fundo: str = "#0E1117",
        colormap: str = "viridis"
    ) -> Optional[io.BytesIO]:
        """Gera imagem da nuvem de palavras usando WordCloud.
        
        Args:
            frequencias_ou_df: dicionário de {palavra: peso} ou DataFrame com colunas 'termo' e 'frequencia'/'valor_total_estimado'.
            tipo_peso: 'frequencia' ou 'valor' (peso ponderado pelo valor em R$).
        """
        try:
            from wordcloud import WordCloud
        except ImportError:
            return None

        pesos: Dict[str, float] = {}

        if isinstance(frequencias_ou_df, pd.DataFrame):
            col_peso = "valor_total_estimado" if tipo_peso == "valor" and "valor_total_estimado" in frequencias_ou_df.columns else "frequencia"
            for _, r in frequencias_ou_df.iterrows():
                termo = str(r.get("termo", "")).strip()
                val = float(r.get(col_peso, 1.0))
                if termo and val > 0:
                    pesos[termo] = val
        elif isinstance(frequencias_ou_df, dict):
            pesos = {str(k): float(v) for k, v in frequencias_ou_df.items() if float(v) > 0}

        if not pesos:
            return None

        # Se o peso for valor em reais, aplica escala logarítmica suave para não explodir visualmente
        if tipo_peso == "valor":
            pesos_ajustados = {k: math.log10(v + 10) * 10 for k, v in pesos.items()}
        else:
            pesos_ajustados = pesos

        wc = WordCloud(
            width=largura,
            height=altura,
            background_color=fundo,
            colormap=colormap,
            max_words=100,
            prefer_horizontal=0.85,
            collocations=False,
            min_font_size=10
        )
        wc.generate_from_frequencies(pesos_ajustados)

        img_buffer = io.BytesIO()
        wc.to_image().save(img_buffer, format="PNG")
        img_buffer.seek(0)
        return img_buffer
