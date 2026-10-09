"""Módulo de Inteligência Geográfica e Logística para Editais e Demandas Públicas.

Mapeia as 7 Bases Operacionais Estratégicas e os 149 municípios-alvo (raio até 200km),
classifica editais com selos logísticos e calcula prioridade operacional.
"""

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd


def normalize_geo_name(name: Optional[str]) -> str:
    """Normaliza nomes de cidades e estados para correspondência semântica."""
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", name)
    without_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", without_accents.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


# Catálogo das 7 Bases Estratégicas e dos 149 Municípios Alvo
CIDADES_ALVO_DATA: List[Dict[str, Any]] = [
    # ----------------- BASE 1: BRASÍLIA (DF) -----------------
    {"cidade": "Brasília", "uf": "DF", "base": "Brasília", "distancia_km": 0, "faixa_raio": "0 km (Base Central)", "porte": "Metrópole", "prioridade": 1, "regiao": "Centro-Oeste"},
    {"cidade": "Águas Lindas de Goiás", "uf": "GO", "base": "Brasília", "distancia_km": 50, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Centro-Oeste"},
    {"cidade": "Valparaíso de Goiás", "uf": "GO", "base": "Brasília", "distancia_km": 35, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Centro-Oeste"},
    {"cidade": "Luziânia", "uf": "GO", "base": "Brasília", "distancia_km": 60, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Centro-Oeste"},
    {"cidade": "Formosa", "uf": "GO", "base": "Brasília", "distancia_km": 75, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Centro-Oeste"},
    {"cidade": "Novo Gama", "uf": "GO", "base": "Brasília", "distancia_km": 40, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Centro-Oeste"},
    {"cidade": "Cidade Ocidental", "uf": "GO", "base": "Brasília", "distancia_km": 45, "faixa_raio": "Até 50 km", "porte": "Médio", "prioridade": 1, "regiao": "Centro-Oeste"},
    {"cidade": "Planaltina", "uf": "GO", "base": "Brasília", "distancia_km": 65, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Centro-Oeste"},
    {"cidade": "Santo Antônio do Descoberto", "uf": "GO", "base": "Brasília", "distancia_km": 50, "faixa_raio": "Até 50 km", "porte": "Médio", "prioridade": 1, "regiao": "Centro-Oeste"},
    {"cidade": "Cristalina", "uf": "GO", "base": "Brasília", "distancia_km": 130, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Centro-Oeste"},
    {"cidade": "Unaí", "uf": "MG", "base": "Brasília", "distancia_km": 165, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Sudeste"},
    {"cidade": "Paracatu", "uf": "MG", "base": "Brasília", "distancia_km": 200, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Sudeste"},
    {"cidade": "Padre Bernardo", "uf": "GO", "base": "Brasília", "distancia_km": 110, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Centro-Oeste"},
    {"cidade": "Alexânia", "uf": "GO", "base": "Brasília", "distancia_km": 90, "faixa_raio": "50 a 100 km", "porte": "Médio", "prioridade": 2, "regiao": "Centro-Oeste"},
    {"cidade": "Cocalzinho de Goiás", "uf": "GO", "base": "Brasília", "distancia_km": 105, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Centro-Oeste"},
    {"cidade": "Abadiânia", "uf": "GO", "base": "Brasília", "distancia_km": 115, "faixa_raio": "100 a 200 km", "porte": "Pequeno", "prioridade": 3, "regiao": "Centro-Oeste"},
    {"cidade": "Pirenópolis", "uf": "GO", "base": "Brasília", "distancia_km": 150, "faixa_raio": "100 a 200 km", "porte": "Pequeno", "prioridade": 3, "regiao": "Centro-Oeste"},
    {"cidade": "Corumbá de Goiás", "uf": "GO", "base": "Brasília", "distancia_km": 130, "faixa_raio": "100 a 200 km", "porte": "Pequeno", "prioridade": 3, "regiao": "Centro-Oeste"},

    # ----------------- BASE 2: GOIÂNIA (GO) -----------------
    {"cidade": "Goiânia", "uf": "GO", "base": "Goiânia", "distancia_km": 0, "faixa_raio": "0 km (Base Central)", "porte": "Metrópole", "prioridade": 1, "regiao": "Centro-Oeste"},
    {"cidade": "Aparecida de Goiânia", "uf": "GO", "base": "Goiânia", "distancia_km": 15, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Centro-Oeste"},
    {"cidade": "Anápolis", "uf": "GO", "base": "Goiânia", "distancia_km": 55, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Centro-Oeste"},
    {"cidade": "Senador Canedo", "uf": "GO", "base": "Goiânia", "distancia_km": 20, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Centro-Oeste"},
    {"cidade": "Trindade", "uf": "GO", "base": "Goiânia", "distancia_km": 25, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Centro-Oeste"},
    {"cidade": "Goianira", "uf": "GO", "base": "Goiânia", "distancia_km": 30, "faixa_raio": "Até 50 km", "porte": "Médio", "prioridade": 1, "regiao": "Centro-Oeste"},
    {"cidade": "Bela Vista de Goiás", "uf": "GO", "base": "Goiânia", "distancia_km": 50, "faixa_raio": "Até 50 km", "porte": "Médio", "prioridade": 1, "regiao": "Centro-Oeste"},
    {"cidade": "Inhumas", "uf": "GO", "base": "Goiânia", "distancia_km": 45, "faixa_raio": "Até 50 km", "porte": "Médio", "prioridade": 1, "regiao": "Centro-Oeste"},
    {"cidade": "Nerópolis", "uf": "GO", "base": "Goiânia", "distancia_km": 35, "faixa_raio": "Até 50 km", "porte": "Médio", "prioridade": 1, "regiao": "Centro-Oeste"},
    {"cidade": "Guapó", "uf": "GO", "base": "Goiânia", "distancia_km": 35, "faixa_raio": "Até 50 km", "porte": "Pequeno", "prioridade": 1, "regiao": "Centro-Oeste"},
    {"cidade": "Morrinhos", "uf": "GO", "base": "Goiânia", "distancia_km": 130, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Centro-Oeste"},
    {"cidade": "Caldas Novas", "uf": "GO", "base": "Goiânia", "distancia_km": 170, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Centro-Oeste"},
    {"cidade": "Itumbiara", "uf": "GO", "base": "Goiânia", "distancia_km": 205, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Centro-Oeste"},
    {"cidade": "Rio Verde", "uf": "GO", "base": "Goiânia", "distancia_km": 230, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Centro-Oeste"},
    {"cidade": "Catalão", "uf": "GO", "base": "Goiânia", "distancia_km": 260, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Centro-Oeste"},
    {"cidade": "Jataí", "uf": "GO", "base": "Goiânia", "distancia_km": 320, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Centro-Oeste"},
    {"cidade": "Goiatuba", "uf": "GO", "base": "Goiânia", "distancia_km": 175, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Centro-Oeste"},
    {"cidade": "Jaraguá", "uf": "GO", "base": "Goiânia", "distancia_km": 125, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Centro-Oeste"},
    {"cidade": "Ceres", "uf": "GO", "base": "Goiânia", "distancia_km": 180, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Centro-Oeste"},

    # ----------------- BASE 3: JOINVILLE (SC) / CURITIBA (PR) -----------------
    {"cidade": "Joinville", "uf": "SC", "base": "Joinville", "distancia_km": 0, "faixa_raio": "0 km (Base Central)", "porte": "Grande", "prioridade": 1, "regiao": "Sul"},
    {"cidade": "Jaraguá do Sul", "uf": "SC", "base": "Joinville", "distancia_km": 35, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sul"},
    {"cidade": "Guaramirim", "uf": "SC", "base": "Joinville", "distancia_km": 30, "faixa_raio": "Até 50 km", "porte": "Médio", "prioridade": 1, "regiao": "Sul"},
    {"cidade": "São Francisco do Sul", "uf": "SC", "base": "Joinville", "distancia_km": 45, "faixa_raio": "Até 50 km", "porte": "Médio", "prioridade": 1, "regiao": "Sul"},
    {"cidade": "Araquari", "uf": "SC", "base": "Joinville", "distancia_km": 25, "faixa_raio": "Até 50 km", "porte": "Médio", "prioridade": 1, "regiao": "Sul"},
    {"cidade": "São Bento do Sul", "uf": "SC", "base": "Joinville", "distancia_km": 80, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sul"},
    {"cidade": "Rio Negrinho", "uf": "SC", "base": "Joinville", "distancia_km": 95, "faixa_raio": "50 a 100 km", "porte": "Médio", "prioridade": 2, "regiao": "Sul"},
    {"cidade": "Blumenau", "uf": "SC", "base": "Joinville", "distancia_km": 100, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sul"},
    {"cidade": "Itajaí", "uf": "SC", "base": "Joinville", "distancia_km": 90, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sul"},
    {"cidade": "Balneário Camboriú", "uf": "SC", "base": "Joinville", "distancia_km": 95, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sul"},
    {"cidade": "Brusque", "uf": "SC", "base": "Joinville", "distancia_km": 105, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Sul"},
    {"cidade": "Navegantes", "uf": "SC", "base": "Joinville", "distancia_km": 85, "faixa_raio": "50 a 100 km", "porte": "Médio", "prioridade": 2, "regiao": "Sul"},
    {"cidade": "Gaspar", "uf": "SC", "base": "Joinville", "distancia_km": 100, "faixa_raio": "50 a 100 km", "porte": "Médio", "prioridade": 2, "regiao": "Sul"},
    {"cidade": "Indaial", "uf": "SC", "base": "Joinville", "distancia_km": 115, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Sul"},
    {"cidade": "Pomerode", "uf": "SC", "base": "Joinville", "distancia_km": 85, "faixa_raio": "50 a 100 km", "porte": "Médio", "prioridade": 2, "regiao": "Sul"},
    {"cidade": "Florianópolis", "uf": "SC", "base": "Joinville", "distancia_km": 180, "faixa_raio": "100 a 200 km", "porte": "Metrópole", "prioridade": 3, "regiao": "Sul"},
    {"cidade": "São José", "uf": "SC", "base": "Joinville", "distancia_km": 175, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Sul"},
    {"cidade": "Palhoça", "uf": "SC", "base": "Joinville", "distancia_km": 185, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Sul"},
    {"cidade": "Biguaçu", "uf": "SC", "base": "Joinville", "distancia_km": 170, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Sul"},
    {"cidade": "Curitiba", "uf": "PR", "base": "Joinville", "distancia_km": 130, "faixa_raio": "100 a 200 km", "porte": "Metrópole", "prioridade": 2, "regiao": "Sul"},
    {"cidade": "São José dos Pinhais", "uf": "PR", "base": "Joinville", "distancia_km": 110, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 2, "regiao": "Sul"},
    {"cidade": "Araucária", "uf": "PR", "base": "Joinville", "distancia_km": 125, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 2, "regiao": "Sul"},
    {"cidade": "Colombo", "uf": "PR", "base": "Joinville", "distancia_km": 140, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Sul"},
    {"cidade": "Pinhais", "uf": "PR", "base": "Joinville", "distancia_km": 125, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 2, "regiao": "Sul"},
    {"cidade": "Campo Largo", "uf": "PR", "base": "Joinville", "distancia_km": 140, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Sul"},
    {"cidade": "Fazenda Rio Grande", "uf": "PR", "base": "Joinville", "distancia_km": 115, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 2, "regiao": "Sul"},
    {"cidade": "Paranaguá", "uf": "PR", "base": "Joinville", "distancia_km": 135, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Sul"},

    # ----------------- BASE 4: SÃO PAULO (SP) -----------------
    {"cidade": "São Paulo", "uf": "SP", "base": "São Paulo", "distancia_km": 0, "faixa_raio": "0 km (Base Central)", "porte": "Metrópole", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Guarulhos", "uf": "SP", "base": "São Paulo", "distancia_km": 20, "faixa_raio": "Até 50 km", "porte": "Metrópole", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "São Bernardo do Campo", "uf": "SP", "base": "São Paulo", "distancia_km": 20, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Santo André", "uf": "SP", "base": "São Paulo", "distancia_km": 18, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Osasco", "uf": "SP", "base": "São Paulo", "distancia_km": 16, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Mauá", "uf": "SP", "base": "São Paulo", "distancia_km": 28, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Mogi das Cruzes", "uf": "SP", "base": "São Paulo", "distancia_km": 50, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Diadema", "uf": "SP", "base": "São Paulo", "distancia_km": 17, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Carapicuíba", "uf": "SP", "base": "São Paulo", "distancia_km": 22, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Barueri", "uf": "SP", "base": "São Paulo", "distancia_km": 26, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Santana de Parnaíba", "uf": "SP", "base": "São Paulo", "distancia_km": 35, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Cotia", "uf": "SP", "base": "São Paulo", "distancia_km": 32, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Taboão da Serra", "uf": "SP", "base": "São Paulo", "distancia_km": 18, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Suzano", "uf": "SP", "base": "São Paulo", "distancia_km": 36, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Itapecerica da Serra", "uf": "SP", "base": "São Paulo", "distancia_km": 33, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Santos", "uf": "SP", "base": "São Paulo", "distancia_km": 75, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "São Vicente", "uf": "SP", "base": "São Paulo", "distancia_km": 72, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "Praia Grande", "uf": "SP", "base": "São Paulo", "distancia_km": 78, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "Guarujá", "uf": "SP", "base": "São Paulo", "distancia_km": 85, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "Cubatão", "uf": "SP", "base": "São Paulo", "distancia_km": 60, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "São José dos Campos", "uf": "SP", "base": "São Paulo", "distancia_km": 85, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "Jacareí", "uf": "SP", "base": "São Paulo", "distancia_km": 75, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "Taubaté", "uf": "SP", "base": "São Paulo", "distancia_km": 130, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Sudeste"},
    {"cidade": "Pindamonhangaba", "uf": "SP", "base": "São Paulo", "distancia_km": 145, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Sudeste"},
    {"cidade": "Guaratinguetá", "uf": "SP", "base": "São Paulo", "distancia_km": 175, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Sudeste"},

    # ----------------- BASE 5: CAMPINAS (SP) / SUL DE MINAS -----------------
    {"cidade": "Campinas", "uf": "SP", "base": "Campinas", "distancia_km": 0, "faixa_raio": "0 km (Base Central)", "porte": "Metrópole", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Sumaré", "uf": "SP", "base": "Campinas", "distancia_km": 25, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Indaiatuba", "uf": "SP", "base": "Campinas", "distancia_km": 28, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Americana", "uf": "SP", "base": "Campinas", "distancia_km": 35, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Hortolândia", "uf": "SP", "base": "Campinas", "distancia_km": 20, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Santa Bárbara d'Oeste", "uf": "SP", "base": "Campinas", "distancia_km": 40, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Paulínia", "uf": "SP", "base": "Campinas", "distancia_km": 18, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Valinhos", "uf": "SP", "base": "Campinas", "distancia_km": 12, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Vinhedo", "uf": "SP", "base": "Campinas", "distancia_km": 20, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Itatiba", "uf": "SP", "base": "Campinas", "distancia_km": 32, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Jundiaí", "uf": "SP", "base": "Campinas", "distancia_km": 40, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Piracicaba", "uf": "SP", "base": "Campinas", "distancia_km": 70, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "Limeira", "uf": "SP", "base": "Campinas", "distancia_km": 55, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "Rio Claro", "uf": "SP", "base": "Campinas", "distancia_km": 85, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "Sorocaba", "uf": "SP", "base": "Campinas", "distancia_km": 85, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "Itu", "uf": "SP", "base": "Campinas", "distancia_km": 45, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Salto", "uf": "SP", "base": "Campinas", "distancia_km": 40, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Sudeste"},
    {"cidade": "Bragança Paulista", "uf": "SP", "base": "Campinas", "distancia_km": 70, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "Atibaia", "uf": "SP", "base": "Campinas", "distancia_km": 65, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "Araras", "uf": "SP", "base": "Campinas", "distancia_km": 90, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "Mogi Guaçu", "uf": "SP", "base": "Campinas", "distancia_km": 70, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "Mogi Mirim", "uf": "SP", "base": "Campinas", "distancia_km": 65, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "São Carlos", "uf": "SP", "base": "Campinas", "distancia_km": 140, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Sudeste"},
    {"cidade": "Extrema", "uf": "MG", "base": "Campinas", "distancia_km": 95, "faixa_raio": "50 a 100 km", "porte": "Médio", "prioridade": 2, "regiao": "Sudeste"},
    {"cidade": "Pouso Alegre", "uf": "MG", "base": "Campinas", "distancia_km": 160, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Sudeste"},
    {"cidade": "Poços de Caldas", "uf": "MG", "base": "Campinas", "distancia_km": 150, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Sudeste"},
    {"cidade": "Itajubá", "uf": "MG", "base": "Campinas", "distancia_km": 180, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Sudeste"},
    {"cidade": "Camanducaia", "uf": "MG", "base": "Campinas", "distancia_km": 110, "faixa_raio": "100 a 200 km", "porte": "Pequeno", "prioridade": 3, "regiao": "Sudeste"},

    # ----------------- BASE 6: RECIFE (PE) / PARAÍBA SUL -----------------
    {"cidade": "Recife", "uf": "PE", "base": "Recife", "distancia_km": 0, "faixa_raio": "0 km (Base Central)", "porte": "Metrópole", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "Jaboatão dos Guararapes", "uf": "PE", "base": "Recife", "distancia_km": 18, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "Olinda", "uf": "PE", "base": "Recife", "distancia_km": 10, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "Paulista", "uf": "PE", "base": "Recife", "distancia_km": 20, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "Camaragibe", "uf": "PE", "base": "Recife", "distancia_km": 16, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "Cabo de Santo Agostinho", "uf": "PE", "base": "Recife", "distancia_km": 35, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "Igarassu", "uf": "PE", "base": "Recife", "distancia_km": 30, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "São Lourenço da Mata", "uf": "PE", "base": "Recife", "distancia_km": 25, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "Abreu e Lima", "uf": "PE", "base": "Recife", "distancia_km": 22, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "Ipojuca", "uf": "PE", "base": "Recife", "distancia_km": 50, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "Vitória de Santo Antão", "uf": "PE", "base": "Recife", "distancia_km": 50, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "Gravatá", "uf": "PE", "base": "Recife", "distancia_km": 85, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Nordeste"},
    {"cidade": "Bezerros", "uf": "PE", "base": "Recife", "distancia_km": 105, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Nordeste"},
    {"cidade": "Caruaru", "uf": "PE", "base": "Recife", "distancia_km": 135, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Nordeste"},
    {"cidade": "Goiana", "uf": "PE", "base": "Recife", "distancia_km": 65, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Nordeste"},
    {"cidade": "Carpina", "uf": "PE", "base": "Recife", "distancia_km": 55, "faixa_raio": "50 a 100 km", "porte": "Grande", "prioridade": 2, "regiao": "Nordeste"},
    {"cidade": "Escada", "uf": "PE", "base": "Recife", "distancia_km": 60, "faixa_raio": "50 a 100 km", "porte": "Médio", "prioridade": 2, "regiao": "Nordeste"},
    {"cidade": "Palmares", "uf": "PE", "base": "Recife", "distancia_km": 120, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Nordeste"},
    {"cidade": "João Pessoa", "uf": "PB", "base": "Recife", "distancia_km": 120, "faixa_raio": "100 a 200 km", "porte": "Metrópole", "prioridade": 2, "regiao": "Nordeste"},
    {"cidade": "Santa Rita", "uf": "PB", "base": "Recife", "distancia_km": 125, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 2, "regiao": "Nordeste"},
    {"cidade": "Bayeux", "uf": "PB", "base": "Recife", "distancia_km": 120, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 2, "regiao": "Nordeste"},
    {"cidade": "Cabedelo", "uf": "PB", "base": "Recife", "distancia_km": 135, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Nordeste"},
    {"cidade": "Conde", "uf": "PB", "base": "Recife", "distancia_km": 105, "faixa_raio": "100 a 200 km", "porte": "Pequeno", "prioridade": 3, "regiao": "Nordeste"},

    # ----------------- BASE 7: NATAL (RN) / PARAÍBA NORTE -----------------
    {"cidade": "Natal", "uf": "RN", "base": "Natal", "distancia_km": 0, "faixa_raio": "0 km (Base Central)", "porte": "Grande", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "Parnamirim", "uf": "RN", "base": "Natal", "distancia_km": 15, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "São Gonçalo do Amarante", "uf": "RN", "base": "Natal", "distancia_km": 20, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "Macaíba", "uf": "RN", "base": "Natal", "distancia_km": 25, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "Ceará-Mirim", "uf": "RN", "base": "Natal", "distancia_km": 35, "faixa_raio": "Até 50 km", "porte": "Grande", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "Extremoz", "uf": "RN", "base": "Natal", "distancia_km": 20, "faixa_raio": "Até 50 km", "porte": "Médio", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "São José de Mipibu", "uf": "RN", "base": "Natal", "distancia_km": 35, "faixa_raio": "Até 50 km", "porte": "Médio", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "Nísia Floresta", "uf": "RN", "base": "Natal", "distancia_km": 40, "faixa_raio": "Até 50 km", "porte": "Pequeno", "prioridade": 1, "regiao": "Nordeste"},
    {"cidade": "Goianinha", "uf": "RN", "base": "Natal", "distancia_km": 55, "faixa_raio": "50 a 100 km", "porte": "Médio", "prioridade": 2, "regiao": "Nordeste"},
    {"cidade": "Canguaretama", "uf": "RN", "base": "Natal", "distancia_km": 75, "faixa_raio": "50 a 100 km", "porte": "Médio", "prioridade": 2, "regiao": "Nordeste"},
    {"cidade": "Touros", "uf": "RN", "base": "Natal", "distancia_km": 90, "faixa_raio": "50 a 100 km", "porte": "Médio", "prioridade": 2, "regiao": "Nordeste"},
    {"cidade": "Nova Cruz", "uf": "RN", "base": "Natal", "distancia_km": 100, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Nordeste"},
    {"cidade": "Santa Cruz", "uf": "RN", "base": "Natal", "distancia_km": 115, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Nordeste"},
    {"cidade": "Currais Novos", "uf": "RN", "base": "Natal", "distancia_km": 180, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Nordeste"},
    {"cidade": "Assú", "uf": "RN", "base": "Natal", "distancia_km": 210, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Nordeste"},
    {"cidade": "Mossoró", "uf": "RN", "base": "Natal", "distancia_km": 280, "faixa_raio": "Polo Regional", "porte": "Grande", "prioridade": 3, "regiao": "Nordeste"},
    {"cidade": "Caicó", "uf": "RN", "base": "Natal", "distancia_km": 280, "faixa_raio": "Polo Regional", "porte": "Médio", "prioridade": 3, "regiao": "Nordeste"},
    {"cidade": "Mamanguape", "uf": "PB", "base": "Natal", "distancia_km": 110, "faixa_raio": "100 a 200 km", "porte": "Médio", "prioridade": 3, "regiao": "Nordeste"},
    {"cidade": "Rio Tinto", "uf": "PB", "base": "Natal", "distancia_km": 120, "faixa_raio": "100 a 200 km", "porte": "Pequeno", "prioridade": 3, "regiao": "Nordeste"},
    {"cidade": "Guarabira", "uf": "PB", "base": "Natal", "distancia_km": 160, "faixa_raio": "100 a 200 km", "porte": "Grande", "prioridade": 3, "regiao": "Nordeste"},
]


class GeoIntelligence:
    def __init__(self, data: Optional[List[Dict[str, Any]]] = None):
        self.raw_data = data or CIDADES_ALVO_DATA
        self.df = pd.DataFrame(self.raw_data)
        self._indexed_cities = {}
        for row in self.raw_data:
            key = (normalize_geo_name(row["cidade"]), row["uf"].upper())
            self._indexed_cities[key] = row

    def get_dataframe(self) -> pd.DataFrame:
        """Retorna o DataFrame de municípios estratégicos."""
        return self.df.copy()

    def export_datasets(self, output_dirs: Optional[List[str]] = None) -> Dict[str, str]:
        """Exporta os dados das 149 cidades alvo para CSV e JSON em diretórios de destino."""
        if output_dirs is None:
            output_dirs = ["data/bases_logisticas", "pncp_intelligence/data/bases_logisticas"]

        exported_paths = {}
        for d in output_dirs:
            p = Path(d)
            p.mkdir(parents=True, exist_ok=True)
            csv_path = p / "cidades_alvo.csv"
            json_path = p / "cidades_alvo.json"

            self.df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(self.raw_data, f, ensure_ascii=False, indent=2)

            exported_paths[f"{d}_csv"] = str(csv_path)
            exported_paths[f"{d}_json"] = str(json_path)

        return exported_paths

    def match_localidade(
        self,
        municipio: Optional[str],
        uf: Optional[str],
        objeto_texto: Optional[str] = None
    ) -> Dict[str, Any]:
        """Avalia localidade de um edital e gera selo e priorização logística."""
        norm_mun = normalize_geo_name(municipio)
        norm_uf = (uf or "").strip().upper()
        norm_obj = normalize_geo_name(objeto_texto)

        # 1. Checa viabilidade 100% Remoto (SaaS, Nuvem, Plataforma Digital, EAD)
        is_remoto = False
        termos_remoto = ["100% remoto", "prestacao remota", "plataforma digital", "software como servico", "saas", "ambiente virtual", "nuvem", "cloud"]
        if any(t in norm_obj for t in termos_remoto):
            is_remoto = True

        # 2. Match direto na base de 149 cidades
        match_key = (norm_mun, norm_uf)
        if match_key in self._indexed_cities:
            cidade_info = self._indexed_cities[match_key]
            dist = cidade_info["distancia_km"]
            base = cidade_info["base"]
            cidade = cidade_info["cidade"]
            estado = cidade_info["uf"]

            if dist == 0:
                selo = f"[BASE DIRETA: {base.upper()}/{estado}]"
            else:
                selo = f"[BASE: {base.upper()} | {cidade}/{estado} ({dist}km)]"

            return {
                "matched": True,
                "is_priority_geo": True,
                "selo": selo,
                "base": base,
                "cidade": cidade,
                "uf": estado,
                "distancia_km": dist,
                "faixa_raio": cidade_info["faixa_raio"],
                "porte": cidade_info["porte"],
                "prioridade": cidade_info["prioridade"],
                "regiao": cidade_info["regiao"],
                "is_remoto": is_remoto,
            }

        # 3. Match parcial por UF de Base Estratégica (DF, GO, SC, PR, SP, MG, PE, RN, PB)
        ufs_estrategicas = {"DF": "Brasília", "GO": "Goiânia", "SC": "Joinville", "PR": "Joinville/Curitiba", "SP": "São Paulo/Campinas", "MG": "Campinas/Sul de Minas", "PE": "Recife", "PB": "Recife/Natal", "RN": "Natal"}
        if norm_uf in ufs_estrategicas:
            selo = f"[ESTADO ALVO: {norm_uf}]"
            if is_remoto:
                selo = f"[VIABILIDADE: 100% REMOTO] {selo}"

            return {
                "matched": True,
                "is_priority_geo": False,
                "selo": selo,
                "base": ufs_estrategicas[norm_uf],
                "cidade": municipio or "",
                "uf": norm_uf,
                "distancia_km": 250,
                "faixa_raio": "Estado Alvo",
                "porte": "Outro",
                "prioridade": 4,
                "regiao": "Alvo",
                "is_remoto": is_remoto,
            }

        # 4. Outras localidades
        selo = "[VIABILIDADE: 100% REMOTO]" if is_remoto else "[FORA DAS BASES]"
        return {
            "matched": is_remoto,
            "is_priority_geo": False,
            "selo": selo,
            "base": "Remoto" if is_remoto else "Outro",
            "cidade": municipio or "",
            "uf": norm_uf,
            "distancia_km": 999,
            "faixa_raio": "Fora do Raio",
            "porte": "Outro",
            "prioridade": 5,
            "regiao": "Brasil",
            "is_remoto": is_remoto,
        }
