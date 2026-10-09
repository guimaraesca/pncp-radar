"""Cliente HTTP oficial para APIs do PNCP (Portal Nacional de Contratações Públicas).

Implementa:
- Tratamento de rate limiting e indisponibilidade com backoff exponencial.
- Endpoints de consulta de publicações, propostas abertas e itens de compras.
- Sanitização de respostas e timeouts controlados.
"""

import logging
import time
from typing import Any, Dict, List, Optional
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("PNCPClient")


class PNCPClient:
    def __init__(
        self,
        consulta_base_url: str = "https://pncp.gov.br/api/consulta/v1",
        pncp_base_url: str = "https://pncp.gov.br/api/pncp/v1",
        timeout: int = 25,
        max_retries: int = 4,
        backoff_factor: float = 2.0,
        rate_limit_delay: float = 0.65,
    ):
        self.consulta_base_url = consulta_base_url.rstrip("/")
        self.pncp_base_url = pncp_base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.rate_limit_delay = rate_limit_delay

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })

    def _request_with_retry(self, method: str, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """Executa requisição HTTP com tentativas e backoff exponencial."""
        delay = self.backoff_factor

        for attempt in range(1, self.max_retries + 1):
            try:
                # Respeita intervalo de requisições para evitar 429
                if self.rate_limit_delay > 0:
                    time.sleep(self.rate_limit_delay)

                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    timeout=self.timeout
                )

                # Sucesso
                if response.status_code == 200:
                    try:
                        return response.json()
                    except Exception:
                        return response.content

                # Caso 204 (Sem registros no período) ou 404 (não encontrado)
                if response.status_code in (204, 404):
                    return None

                # Caso Rate Limit (429) - aplica pausa mais generosa
                if response.status_code == 429:
                    sleep_time = max(delay, 5.0)
                    logger.warning(
                        f"Rate Limit (429) no PNCP em {url} (Tentativa {attempt}/{self.max_retries}). Pausando {sleep_time:.1f}s..."
                    )
                    time.sleep(sleep_time)
                    delay *= 2
                    continue

                # Erros temporários de infraestrutura (5xx)
                if response.status_code in (500, 502, 503, 504):
                    logger.warning(
                        f"Status {response.status_code} na URL {url} (Tentativa {attempt}/{self.max_retries}). Aguardando {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= 2
                    continue

                logger.error(f"Erro inesperado HTTP {response.status_code} na URL {url}: {response.text[:200]}")
                return None

            except (requests.ConnectionError, requests.Timeout) as e:
                logger.warning(f"Erro de conexão ({type(e).__name__}) em {url} (Tentativa {attempt}/{self.max_retries}). Aguardando {delay:.1f}s...")
                time.sleep(delay)
                delay *= 2
            except Exception as e:
                logger.error(f"Falha de requisição em {url}: {e}")
                return None

        logger.error(f"Número máximo de tentativas excedido para a URL: {url}")
        return None

    def get_publicacoes(
        self,
        data_inicial: str,
        data_final: str,
        codigo_modalidade: int,
        pagina: int = 1,
        tamanho_pagina: int = 50,
        uf: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Consulta contratações por período de publicação e modalidade.
        
        Args:
            data_inicial: Data no formato AAAAMMDD (ex: '20240101')
            data_final: Data no formato AAAAMMDD (ex: '20240115')
            codigo_modalidade: Código numérico (ex: 6 para Pregão, 8 para Dispensa)
            pagina: Número da página (inicia em 1)
            tamanho_pagina: Registros por página (máx 50)
            uf: Opcional, sigla do estado
        """
        url = f"{self.consulta_base_url}/contratacoes/publicacao"
        params: Dict[str, Any] = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigoModalidadeContratacao": codigo_modalidade,
            "pagina": pagina,
            "tamanhoPagina": tamanho_pagina,
        }
        if uf:
            params["uf"] = uf

        return self._request_with_retry("GET", url, params=params)

    def get_propostas_abertas(
        self,
        data_final: str,
        codigo_modalidade: Optional[int] = None,
        pagina: int = 1,
        tamanho_pagina: int = 50,
        uf: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Consulta contratações com recebimento de proposta atualmente aberto."""
        url = f"{self.consulta_base_url}/contratacoes/proposta"
        params: Dict[str, Any] = {
            "dataFinal": data_final,
            "pagina": pagina,
            "tamanhoPagina": tamanho_pagina,
        }
        if codigo_modalidade:
            params["codigoModalidadeContratacao"] = codigo_modalidade
        if uf:
            params["uf"] = uf

        return self._request_with_retry("GET", url, params=params)

    def get_itens_compra(self, cnpj: str, ano: int, sequencial: int) -> Optional[List[Dict[str, Any]]]:
        """Obtém a lista detalhada de itens de uma compra/edital."""
        clean_cnpj = "".join(filter(str.isdigit, str(cnpj)))
        url = f"{self.pncp_base_url}/orgaos/{clean_cnpj}/compras/{ano}/{sequencial}/itens"
        # Para itens, usa timeout menor para não travar o crawler caso o órgão esteja instável
        old_timeout = self.timeout
        old_retries = self.max_retries
        try:
            self.timeout = 10
            self.max_retries = 2
            res = self._request_with_retry("GET", url)
            if isinstance(res, list):
                return res
            return []
        finally:
            self.timeout = old_timeout
            self.max_retries = old_retries

    def get_arquivos_compra(self, cnpj: str, ano: int, sequencial: int) -> Optional[List[Dict[str, Any]]]:
        """Consulta os metadados dos arquivos/documentos (Edital, Termo de Referência)."""
        clean_cnpj = "".join(filter(str.isdigit, str(cnpj)))
        url = f"{self.pncp_base_url}/orgaos/{clean_cnpj}/compras/{ano}/{sequencial}/arquivos"
        res = self._request_with_retry("GET", url)
        if isinstance(res, list):
            return res
        return []

    def download_arquivo_binario(self, cnpj: str, ano: int, sequencial: int, sequencial_documento: int, dest_path: str) -> bool:
        """Baixa o arquivo binário (PDF, DOCX, ZIP) do edital ou termo de referência."""
        clean_cnpj = "".join(filter(str.isdigit, str(cnpj)))
        url = f"{self.pncp_base_url}/orgaos/{clean_cnpj}/compras/{ano}/{sequencial}/arquivos/{sequencial_documento}"
        try:
            res = self.session.get(url, timeout=self.timeout)
            if res.status_code == 200 and len(res.content) > 0:
                Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
                with open(dest_path, "wb") as f:
                    f.write(res.content)
                return True
        except Exception as e:
            logger.warning(f"Erro ao baixar arquivo {url}: {e}")
        return False
