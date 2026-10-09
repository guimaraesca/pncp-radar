"""Módulo central de formatação numérica e financeira no padrão brasileiro (BRL / pt-BR).

Fornece funções para exibição elegante de:
- Moeda completa: R$ 1.234.567,89 (ponto para milhar, vírgula para decimal)
- Moeda compacta legível para grandes números: R$ 1,85 Bi, R$ 45,20 Mi, R$ 750,0 Mil
- Números inteiros: 1.670, 25.400
- Percentuais: 12,5%
"""

from typing import Optional, Union


def formatar_inteiro(valor: Union[int, float, None]) -> str:
    """Formata número inteiro no padrão brasileiro com ponto separador de milhar.
    
    Exemplo: 1234567 -> '1.234.567'
    """
    if valor is None:
        return "0"
    try:
        val_int = int(round(float(valor)))
        return f"{val_int:,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def formatar_moeda_completa(valor: Union[int, float, None], prefixo: bool = True) -> str:
    """Formata valor em Reais no formato completo oficial brasileiro.
    
    Exemplo: 1234567.89 -> 'R$ 1.234.567,89'
    """
    if valor is None:
        return "R$ 0,00" if prefixo else "0,00"
    try:
        val_float = float(valor)
        if val_float < 0:
            sinal = "-"
            val_float = abs(val_float)
        else:
            sinal = ""
        
        # Formata com padrão americano provisório e inverte separadores
        partes = f"{val_float:,.2f}".split(".")
        inteiro = partes[0].replace(",", ".")
        decimal = partes[1]
        
        res = f"{sinal}{inteiro},{decimal}"
        return f"R$ {res}" if prefixo else res
    except (ValueError, TypeError):
        return "R$ 0,00" if prefixo else "0,00"


def formatar_moeda_compacta(valor: Union[int, float, None], prefixo: bool = True) -> str:
    """Formata grandes volumes financeiros de forma compacta e intuitiva para tomadores de decisão.
    
    Exemplos:
    - 4_850_000_000 -> 'R$ 4,85 Bi'
    - 120_500_000   -> 'R$ 120,50 Mi'
    - 450_000       -> 'R$ 450,0 Mil'
    - 1_250.50      -> 'R$ 1.250,50'
    - 85.00         -> 'R$ 85,00'
    """
    if valor is None:
        return "R$ 0,00" if prefixo else "0,00"
    try:
        val = float(valor)
        if val < 0:
            sinal = "-"
            val = abs(val)
        else:
            sinal = ""
            
        p = "R$ " if prefixo else ""
        
        if val >= 1_000_000_000:
            bi = val / 1_000_000_000
            texto = f"{bi:.2f}".replace(".", ",")
            return f"{sinal}{p}{texto} Bi"
        elif val >= 1_000_000:
            mi = val / 1_000_000
            texto = f"{mi:.2f}".replace(".", ",")
            return f"{sinal}{p}{texto} Mi"
        elif val >= 100_000:
            mil = val / 1_000
            texto = f"{mil:.1f}".replace(".", ",")
            return f"{sinal}{p}{texto} Mil"
        else:
            # Para valores menores, exibe o valor completo oficial
            return formatar_moeda_completa(val if not sinal else -val, prefixo=prefixo)
    except (ValueError, TypeError):
        return "R$ 0,00" if prefixo else "0,00"


def formatar_moeda(valor: Union[int, float, None], compacto: bool = False, prefixo: bool = True) -> str:
    """Função polivalente de formatação de moeda."""
    if compacto:
        return formatar_moeda_compacta(valor, prefixo=prefixo)
    return formatar_moeda_completa(valor, prefixo=prefixo)


def formatar_percentual(valor: Union[int, float, None], decimais: int = 1) -> str:
    """Formata percentual no formato brasileiro: 15.35 -> '15,4%'."""
    if valor is None:
        return "0,0%"
    try:
        val_float = float(valor)
        fmt = f"{{:.{decimais}f}}".format(val_float)
        return f"{fmt.replace('.', ',')}%"
    except (ValueError, TypeError):
        return "0,0%"
