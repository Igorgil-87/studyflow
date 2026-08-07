"""
tools/github_source.py — repositórios em alta no GitHub (Search API, sem chave).

O GitHub não tem endpoint oficial de "trending". O método consagrado é a
Search API: repositórios criados recentemente, ordenados por estrelas.
  GET /search/repositories?q=created:>YYYY-MM-DD&sort=stars&order=desc

Sem token: limite baixo (~10 req/min na Search API). Por isso CACHEAMOS o
resultado em memória por GITHUB_TTL segundos (default 1800 = 30 min).
Token opcional (GITHUB_TOKEN) eleva o limite, mas não é obrigatório.

Fail-open: erro de rede/limite → retorna o cache antigo (se houver) ou [].
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.parse
import urllib.request

API_URL = "https://api.github.com/search/repositories"

_cache = {"ts": 0.0, "data": []}


def _http_get(url: str, token: str, timeout: int):
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    headers = {
        "User-Agent": "StudyFlow/1.0",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)


def _since_date(days: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() - days * 86400))


def parse_repos(data: dict, limit: int) -> list[dict]:
    if not data or "items" not in data:
        return []
    out = []
    for r in data["items"][:limit]:
        out.append({
            "name": r.get("full_name", ""),
            "desc": (r.get("description") or "")[:140],
            "stars": int(r.get("stargazers_count", 0)),
            "lang": r.get("language") or "",
            "url": r.get("html_url", ""),
            "owner_avatar": (r.get("owner") or {}).get("avatar_url", ""),
        })
    return out


def fetch_trending(days: int = 7, limit: int = 6, lang: str | None = None,
                   token: str | None = None, fetch=None, timeout: int = 12,
                   ttl: int | None = None) -> list[dict]:
    """Repos em alta (criados nos últimos `days` dias, mais estrelados). Cacheado."""
    token = token if token is not None else os.getenv("GITHUB_TOKEN", "")
    ttl = ttl if ttl is not None else int(os.getenv("GITHUB_TTL", "1800"))

    # cache em memória (evita estourar o limite de 10 req/min sem chave)
    if fetch is None and _cache["data"] and (time.time() - _cache["ts"]) < ttl:
        return _cache["data"]

    q = f"created:>{_since_date(days)}"
    if lang:
        q += f" language:{lang}"
    params = urllib.parse.urlencode({"q": q, "sort": "stars", "order": "desc",
                                     "per_page": str(max(limit, 6))})
    url = f"{API_URL}?{params}"

    if fetch is not None:
        data, err = fetch(url, timeout), None
    else:
        data, err = _http_get(url, token, timeout)

    if err:
        print(f"[github] falhou: {err} — usando cache" if _cache["data"] else f"[github] falhou: {err}")
        return _cache["data"]  # fail-open: devolve cache antigo (ou [])

    repos = parse_repos(data, limit)
    if repos and fetch is None:
        _cache["ts"] = time.time()
        _cache["data"] = repos
    return repos
