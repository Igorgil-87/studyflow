"""
tools/x_source.py — fonte de tendências do X (Twitter) via API de terceiro.

Foco: POLÊMICAS e o que está BOMBANDO agora, por assunto. Usa filtros de
engajamento (min_faves) que a API oficial não expõe. Provider padrão:
TwitterAPI.io (US$ 0,15/1k tweets, US$ 1 grátis de teste). Também aceita GetXAPI.

Opcional e fail-open: sem X_API_KEY, retorna vazio e o pipeline segue.

Env:
  X_ENABLED=1
  X_PROVIDER=twitterapi   (twitterapi | getxapi)
  X_API_KEY=...
  X_LANG=pt   X_MIN_FAVES=300   X_MAX_RESULTS=10
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

_ENDPOINTS = {
    "twitterapi": "https://api.twitterapi.io/twitter/tweet/advanced_search",
    "getxapi":    "https://api.getxapi.com/twitter/tweet/advanced_search",
}

# termos que sinalizam polêmica/discussão (PT-BR)
_POLEMIC_TERMS = ("polêmica OR polemica OR treta OR cancelado OR revolta OR "
                  "absurdo OR indignação OR mentira OR escândalo OR escandalo")


def _http_get(url: str, headers: dict, timeout: int):
    import time as _t
    for tentativa in range(3):
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and tentativa < 2:
                _t.sleep(2.5 * (tentativa + 1))   # espera e tenta de novo
                continue
            print(f"[x_source] requisição falhou: {e}")
            return None
        except Exception as e:
            print(f"[x_source] requisição falhou: {e}")
            return None
    return None


def build_query(topic: str, mode: str = "bombando", lang: str = "pt",
                min_faves: int = 300) -> str:
    """Monta a expressão de busca avançada do X."""
    topic = (topic or "").strip()
    parts = [topic] if topic else []
    if mode == "polemica":
        parts.append(f"({_POLEMIC_TERMS})")
    if min_faves and min_faves > 0:
        parts.append(f"min_faves:{min_faves}")
    if lang:
        parts.append(f"lang:{lang}")
    return " ".join(parts)


def _clean_tweet(text: str) -> str:
    t = re.sub(r"https?://\S+", "", text or "")     # tira URLs
    t = re.sub(r"\s+", " ", t).strip()
    return t


def parse_response(data: dict) -> dict:
    """Normaliza a resposta (formato twitterapi.io / getxapi). Puro/testável."""
    if not data:
        return {"topics": [], "context": "", "links": []}
    tweets = data.get("tweets") or data.get("data") or []
    topics, links = [], []
    for tw in tweets:
        text = _clean_tweet(tw.get("text", ""))
        url = tw.get("url") or tw.get("twitterUrl") or ""
        author = (tw.get("author") or {}).get("userName", "")
        likes = tw.get("likeCount", 0) or 0
        if len(text) >= 12:
            topics.append(text[:160])
            if url:
                links.append({"url": url, "title": text[:80],
                              "source": f"@{author}" if author else "x"})
    context = ""
    if topics:
        context = ("X / Twitter (em alta e polêmicas):\n"
                   + "\n".join(f"  • {t}" for t in topics[:8]))
    return {"topics": topics, "context": context, "links": links}


def fetch_x(topic: str, mode: str = "bombando", provider: str | None = None,
            api_key: str | None = None, lang: str | None = None,
            min_faves: int | None = None, max_results: int | None = None,
            fetch=None, timeout: int = 20) -> dict:
    provider = (provider or os.getenv("X_PROVIDER", "twitterapi")).lower()
    api_key = api_key or os.getenv("X_API_KEY")
    if not api_key:
        return {"topics": [], "context": "", "links": []}
    lang = lang or os.getenv("X_LANG", "pt")
    min_faves = min_faves if min_faves is not None else int(os.getenv("X_MIN_FAVES", "50"))

    query = build_query(topic, mode, lang, min_faves)
    base = _ENDPOINTS.get(provider, _ENDPOINTS["twitterapi"])

    if provider == "getxapi":
        params = urllib.parse.urlencode({"q": query, "product": "Latest"})
        headers = {"Authorization": f"Bearer {api_key}"}
    else:  # twitterapi.io
        params = urllib.parse.urlencode({"query": query, "queryType": "Latest"})
        headers = {"X-API-Key": api_key}

    data = (fetch or _http_get)(f"{base}?{params}", headers, timeout)
    out = parse_response(data)
    if max_results:
        out["topics"] = out["topics"][:max_results]
        out["links"] = out["links"][:max_results]
    return out


def fetch_x_trends(category_label: str, niche: str = "") -> dict:
    """Junta o que está BOMBANDO + as POLÊMICAS do X para a categoria."""
    if not os.getenv("X_API_KEY") or os.getenv("X_ENABLED", "1") == "0":
        return {"topics": [], "context": "", "links": []}
    alvo = (category_label + (" " + niche if niche else "")).strip()
    bombando = fetch_x(alvo, mode="bombando")
    time.sleep(2.2)   # respeita o rate limit (evita 429)
    polemica = fetch_x(alvo, mode="polemica")
    topics = (polemica.get("topics", []) or []) + (bombando.get("topics", []) or [])
    links = (polemica.get("links", []) or []) + (bombando.get("links", []) or [])
    ctx = [c for c in (polemica.get("context"), bombando.get("context")) if c]
    # dedup simples por texto
    seen, uniq = set(), []
    for t in topics:
        k = t.lower()[:60]
        if k not in seen:
            seen.add(k)
            uniq.append(t)
    return {"topics": uniq[:12], "context": "\n\n".join(ctx), "links": links[:12]}
