"""
tools/economy_source.py — cotações de economia em tempo real (AwesomeAPI).

Gratuita e brasileira, sem precisar de chave. Devolve dólar, euro, bitcoin
(e o que mais você quiser) com valor e variação percentual — pronto para uma
faixa de cotações estilo canal de economia.

Fail-open: se a rede falhar, retorna lista vazia e a tela segue sem a faixa.
"""

from __future__ import annotations

import json
import urllib.request

AWESOME_URL = "https://economia.awesomeapi.com.br/last/"

# pares padrão da faixa (código AwesomeAPI -> rótulo curto)
DEFAULT_PAIRS = [
    ("USD-BRL", "Dólar"),
    ("EUR-BRL", "Euro"),
    ("BTC-BRL", "Bitcoin"),
    ("GBP-BRL", "Libra"),
    ("ARS-BRL", "Peso ARS"),
]


def _http_get(url: str, timeout: int):
    import ssl
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "StudyFlow/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"[economy] requisição falhou: {e}")
        return None


def parse_response(data: dict, pairs) -> list[dict]:
    """Normaliza a resposta da AwesomeAPI em itens prontos para a faixa."""
    if not data:
        return []
    out = []
    for code, label in pairs:
        key = code.replace("-", "")          # USD-BRL -> USDBRL
        item = data.get(key)
        if not item:
            continue
        try:
            value = float(item.get("bid", 0))
            pct = float(item.get("pctChange", 0))
        except (TypeError, ValueError):
            continue
        out.append({
            "code": code,
            "label": label,
            "value": value,
            "pct": pct,
            "dir": "up" if pct > 0 else ("down" if pct < 0 else "flat"),
        })
    return out


def fetch_quotes(pairs=None, fetch=None, timeout: int = 12) -> list[dict]:
    pairs = pairs or DEFAULT_PAIRS
    codes = ",".join(c for c, _ in pairs)
    data = (fetch or _http_get)(AWESOME_URL + codes, timeout)
    result = parse_response(data, pairs)
    if not result:
        print(f"[economy] câmbio vazio (data={'ok' if data else 'None'}) — "
              "verifique acesso a economia.awesomeapi.com.br")
    else:
        print(f"[economy] câmbio OK: {len(result)} cotações")
    return result


def format_quote(item: dict) -> str:
    """'Dólar R$ 5,73 ▲ 0,4%' — formatação BR para a faixa."""
    v = item["value"]
    # bitcoin e valores altos sem casas decimais; câmbio com 2 casas
    if v >= 1000:
        valor = f"{v:,.0f}".replace(",", ".")
    else:
        valor = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    arrow = "▲" if item["dir"] == "up" else ("▼" if item["dir"] == "down" else "▬")
    pct = f"{abs(item['pct']):.2f}".replace(".", ",")
    prefix = "" if item.get("is_stock") else "R$ "
    return f"{item['label']} {prefix}{valor} {arrow} {pct}%"


# ── Ações brasileiras (brapi.dev) — estilo faixa CNN ──
BRAPI_URL = "https://brapi.dev/api/quote/"
DEFAULT_STOCKS = ["PETR4", "VALE3", "ITUB4", "BBDC4", "B3SA3", "ABEV3", "MGLU3"]


def fetch_stocks(tickers=None, token: str | None = None, fetch=None, timeout: int = 12) -> list[dict]:
    """
    Cotações de ações da B3 com ORQUESTRAÇÃO de fontes (uma falha → outra supre):
      1) yfinance (grátis, sem token) — primário
      2) brapi.dev (se BRAPI_TOKEN definido) — reserva
    Se ambas falharem, retorna vazio e o câmbio sustenta a faixa.
    """
    tickers = tickers or DEFAULT_STOCKS
    # injeção de fetch nos testes pula a orquestração e usa brapi direto
    if fetch is not None:
        return _fetch_stocks_brapi(tickers, token, fetch, timeout)

    via_yf = _fetch_stocks_yfinance(tickers)
    if via_yf:
        return via_yf
    import os
    if os.getenv("BRAPI_TOKEN"):
        return _fetch_stocks_brapi(tickers, token, None, timeout)
    return []


def _fetch_stocks_yfinance(tickers) -> list[dict]:
    """Fonte primária: yfinance (sem token). Tickers da B3 levam sufixo .SA."""
    try:
        import yfinance as yf
    except Exception:
        return []
    out = []
    try:
        symbols = [f"{t}.SA" for t in tickers]
        data = yf.Tickers(" ".join(symbols))
        for t in tickers:
            try:
                info = data.tickers[f"{t}.SA"].fast_info
                price = float(info.get("last_price") or info.get("lastPrice") or 0)
                prev = float(info.get("previous_close") or info.get("previousClose") or 0)
                if not price or not prev:
                    continue
                pct = (price - prev) / prev * 100
                out.append({
                    "code": t, "label": t, "value": price, "pct": round(pct, 2),
                    "is_stock": True,
                    "dir": "up" if pct > 0 else ("down" if pct < 0 else "flat"),
                })
            except Exception:
                continue
    except Exception as e:
        print(f"[economy] yfinance falhou: {e}")
        return []
    return out


def _fetch_stocks_brapi(tickers, token, fetch, timeout) -> list[dict]:
    """Fonte reserva: brapi.dev (exige token)."""
    import os
    token = token or os.getenv("BRAPI_TOKEN", "")
    if not token and fetch is None:
        return []
    url = BRAPI_URL + ",".join(tickers) + (f"?token={token}" if token else "")
    data = (fetch or _http_get)(url, timeout)
    if not data:
        return []
    out = []
    for r in (data.get("results") or []):
        try:
            price = float(r.get("regularMarketPrice", 0))
            pct = float(r.get("regularMarketChangePercent", 0))
        except (TypeError, ValueError):
            continue
        out.append({
            "code": r.get("symbol", ""), "label": r.get("symbol", ""),
            "value": price, "pct": pct, "is_stock": True,
            "dir": "up" if pct > 0 else ("down" if pct < 0 else "flat"),
        })
    return out
