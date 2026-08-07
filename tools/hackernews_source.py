"""
tools/hackernews_source.py — Hacker News Top Stories (API oficial Firebase).

Sem chave, sem rate limit. Padrão N+1:
  1) GET /v0/topstories.json        -> array de IDs (até 500)
  2) GET /v0/item/{id}.json (cada)  -> detalhes da história

Como cada história é uma requisição, buscamos só as primeiras `limit` e
CACHEAMOS em memória por HN_TTL segundos (default 900 = 15 min).

Fail-open: erro de rede → cache antigo (se houver) ou [].
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.request

BASE = "https://hacker-news.firebaseio.com/v0"

_cache = {"ts": 0.0, "data": []}


def _http_get(url: str, timeout: int):
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "StudyFlow/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)


def _domain(url: str) -> str:
    if not url:
        return "news.ycombinator.com"
    try:
        host = url.split("//", 1)[-1].split("/", 1)[0]
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def parse_story(item: dict) -> dict | None:
    if not item or item.get("type") != "story" or not item.get("title"):
        return None
    sid = item.get("id")
    url = item.get("url") or f"https://news.ycombinator.com/item?id={sid}"
    return {
        "title": item.get("title", ""),
        "url": url,
        "domain": _domain(item.get("url", "")),
        "score": int(item.get("score", 0)),
        "comments": int(item.get("descendants", 0)),
        "by": item.get("by", ""),
        "hn_url": f"https://news.ycombinator.com/item?id={sid}",
    }


def fetch_top(limit: int = 6, fetch=None, timeout: int = 10,
              ttl: int | None = None) -> list[dict]:
    """Top stories do Hacker News. Cacheado para evitar muitas requisições."""
    ttl = ttl if ttl is not None else int(os.getenv("HN_TTL", "900"))

    if fetch is None and _cache["data"] and (time.time() - _cache["ts"]) < ttl:
        return _cache["data"]

    getter = fetch if fetch is not None else (lambda u, t: _http_get(u, t)[0])

    # 1) lista de IDs
    ids = getter(f"{BASE}/topstories.json", timeout)
    if not ids or not isinstance(ids, list):
        return _cache["data"]

    # 2) detalhes das primeiras (busca um pouco mais para descartar não-stories)
    stories = []
    for sid in ids[: limit * 2]:
        item = getter(f"{BASE}/item/{sid}.json", timeout)
        st = parse_story(item)
        if st:
            stories.append(st)
        if len(stories) >= limit:
            break

    if stories and fetch is None:
        _cache["ts"] = time.time()
        _cache["data"] = stories
    return stories if stories else _cache["data"]
