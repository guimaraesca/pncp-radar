#!/usr/bin/env python3
"""Script de Sincronização Diária I.C.A.R.O. (Compatibilidade de Entrada).

Este script unifica e executa o ciclo completo de inteligência:
1. Varredura e pontuação de Licitações Públicas (PNCP).
2. Varredura de Agências Multilaterais, Terceiro Setor e Mercado Privado (I.C.A.R.O.).
3. Triagem semântica com Google Gemini.
4. Reexportação de Excel, Parquet e Mapa Interativo.
5. Disparo do Briefing Diário Integrado no Telegram.
"""

import sys
import run_icaro

if __name__ == "__main__":
    sys.exit(run_icaro.main())
