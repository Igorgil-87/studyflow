"""
obs/pricing.py — estimativa de custo por chamada de LLM.

Os preços são aproximados e configuráveis (USD por 1M de tokens). Tokens são
ESTIMADOS via tiktoken (ou heurística len/4 se indisponível), porque as tools
encapsulam a chamada e nem sempre expõem o usage real. Tudo aqui é rotulado
como estimativa — honestidade > precisão falsa.
"""

from __future__ import annotations

# USD por 1.000.000 de tokens (input, output). Ajuste conforme a tabela vigente.
PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini":              (0.15, 0.60),
    "gpt-4o":                   (2.50, 10.00),
    "claude-sonnet-4-6":        (3.00, 15.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
}

# Preço padrão se o modelo não estiver na tabela (evita custo zero silencioso).
_DEFAULT = (1.00, 3.00)


def _price(model: str) -> tuple[float, float]:
    if model in PRICES:
        return PRICES[model]
    for key, val in PRICES.items():       # match por prefixo (ex.: claude-haiku-*)
        if model.startswith(key.split("-2025")[0]):
            return val
    return _DEFAULT


def estimate_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    if not text:
        return 0
    try:
        import tiktoken
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)     # heurística de fallback


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = _price(model)
    return round(
        (input_tokens / 1_000_000) * pin + (output_tokens / 1_000_000) * pout,
        6,
    )
