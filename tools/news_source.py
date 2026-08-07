"""
tools/news_source.py — fonte de manchetes via API de notícias.

Suporta GNews (padrão, tem tier grátis) e NewsData.io, escolhido por env.
Traz manchetes reais COM link — viram fontes nos cards de tendência.

Opcional e fail-open: sem NEWS_API_KEY, retorna vazio.

Env:
  NEWS_PROVIDER = gnews | newsdata   (padrão: gnews)
  NEWS_API_KEY  = sua chave
  NEWS_LANG     = pt   NEWS_COUNTRY = br
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request


def _http_get(url: str, timeout: int):
    import time as _t
    for tentativa in range(3):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and tentativa < 2:
                _t.sleep(2.5 * (tentativa + 1))
                continue
            print(f"[news] requisição falhou: {e}")
            return None
        except Exception as e:
            print(f"[news] requisição falhou: {e}")
            return None
    return None


def parse_response(provider: str, data: dict) -> dict:
    """Normaliza a resposta dos provedores num formato único. Puro/testável."""
    if not data:
        return {"headlines": [], "topics": [], "links": []}
    if provider == "newsdata":
        articles = data.get("results") or []
    else:  # gnews
        articles = data.get("articles") or []

    headlines = []
    for a in articles:
        title = a.get("title")
        url = a.get("url") or a.get("link")
        if provider == "newsdata":
            src = a.get("source_id") or ""
        else:
            src = (a.get("source") or {}).get("name", "")
        if title and url:
            headlines.append({"title": title, "url": url, "source": src})

    links = [{"url": h["url"], "title": h["title"], "source": h["source"] or "news"}
             for h in headlines]
    return {"headlines": headlines, "topics": [h["title"] for h in headlines],
            "links": links}


def fetch_news(query: str, lang: str | None = None, country: str | None = None,
               api_key: str | None = None, provider: str | None = None,
               fetch=None, timeout: int = 15, max_results: int = 6) -> dict:
    provider = (provider or os.getenv("NEWS_PROVIDER", "gnews")).lower()
    api_key = api_key or os.getenv("NEWS_API_KEY")
    if not api_key or not query:
        return {"headlines": [], "topics": [], "links": []}
    lang = lang or os.getenv("NEWS_LANG", "pt")
    country = country or os.getenv("NEWS_COUNTRY", "br")
    q = urllib.parse.quote(query)

    if provider == "newsdata":
        url = (f"https://newsdata.io/api/1/news?apikey={api_key}&q={q}"
               f"&language={lang}&country={country}")
    else:  # gnews
        url = (f"https://gnews.io/api/v4/search?q={q}&lang={lang}"
               f"&country={country}&max={max_results}&apikey={api_key}")

    data = (fetch or _http_get)(url, timeout)
    return parse_response(provider, data)
