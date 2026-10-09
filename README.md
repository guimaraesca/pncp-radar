# 🏛️ Radar PNCP | Inteligência de Compras Públicas & Candidatura

> **Motor de inteligência artificial e DataViz executivo para monitoramento contínuo de contratações sob a Lei 14.133/2021 (Nova Lei de Licitações).**

---

## 🌟 Visão Geral

O **Radar PNCP** é uma plataforma corporativa desenvolvida para monitorar, ranquear e antecipar oportunidades de mercado público em tempo real, cobrindo todo o ecossistema do Portal Nacional de Contratações Públicas (PNCP).

Projetado sob a filosofia **Widescreen Dataviz & Datadriven**, o dashboard sintetiza editais em aberto através de 4 pilares estratégicos:
1. **Histórico da Modalidade** (Pregão Eletrônico, Dispensa, Concorrência)
2. **Aderência Técnica & Fit de Demanda** (SaaS, Inteligência Artificial, Nuvem, GovTech)
3. **Custo-Benefício** (Volume vs Ticket Médio vs Esforço de Disputa)
4. **Logística Operacional** (9 Bases Estratégicas e malha de até 250 km)

---

## 📑 Módulos Executivos

1. **🎯 Radar de Candidatura (Editais Abertos):** Visão central em 3 colunas (Ramificações Sankey, Linha do Tempo Estilo WSJ e Feed Tático com links oficiais no PNCP) conectada a gavetas de inteligência técnica.
2. **⚖️ Análise Quali-Quanti (Risco x Retorno):** Matriz estratégica de 4 quadrantes (🟢 Joias da Coroa, 🔵 Fluxo Contínuo, 🟣 Grandes Apostas, 🔴 Armadilhas) com cálculo do **Índice Sharpe Gov**.
3. **🚀 Estratégia de Produtos (C-Level):** Dimensionamento de mercado (TAM), precificação média por contratação e requisitos técnicos recorrentes em TRs.
4. **📊 Análise Quantitativa:** Sazonalidade, distribuição de modalidades e maiores órgãos compradores.
5. **🏷️ Segmentação Temática:** Treemaps e decomposição orçamentária por verticais de solução.
6. **🧠 Inteligência NLP & Nuvem:** Mineração de texto nos objetos contratuais e identificação de termos estratégicos.
7. **🗺️ Mapa Geo-Temático & Hubs:** Cobertura das 27 capitais e anéis de viabilidade logística.
8. **🔍 Explorador Granular de Editais:** Consulta detalhada de itens unitários e valores de referência.
9. **⚙️ Gestão de Coletas & Expansão:** Exportação para Excel e Parquet e sincronização da base.

---

## 🚀 Como Executar Localmente

```bash
# 1. Clonar repositório
git clone https://github.com/guimaraesca/pncp-radar.git
cd pncp-radar

# 2. Criar ambiente virtual e instalar dependências
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Iniciar o dashboard
streamlit run pncp_intelligence/dashboard/app.py
```

O dashboard estará disponível em `http://localhost:8501`.

---

## ☁️ Hospedagem Online no Streamlit Cloud

1. Conecte sua conta do GitHub no [share.streamlit.io](https://share.streamlit.io).
2. Selecione o repositório `guimaraesca/pncp-radar` e a branch `main`.
3. Defina o arquivo principal como: `pncp_intelligence/dashboard/app.py`.
4. (Opcional) Configure os segredos no painel de Settings do Streamlit:
   ```toml
   TELEGRAM_TOKEN = "seu_token"
   TELEGRAM_CHAT_ID = "seu_chat_id"
   ```

---

## 🤖 Automação Diária (GitHub Actions)

O repositório já inclui um fluxo em `.github/workflows/daily_sync.yml` que:
- Executa diariamente às 07:00 (BRT).
- Coleta novos editais publicados no PNCP.
- Envia o briefing e os alertas de editais recomendados via bot no **Telegram**.
- Atualiza a base de dados SQLite automaticamente.

---

## 📄 Licença & Conformidade

Desenvolvido para análise mercadológica de dados abertos sob a **Lei nº 14.133/2021** e **Lei de Acesso à Informação (Lei 12.527/2011)**.
