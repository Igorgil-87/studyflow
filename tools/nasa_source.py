"""
tools/nasa_source.py — Foto Astronômica do Dia (NASA APOD).

GET https://api.nasa.gov/planetary/apod?api_key=KEY
Retorna: title, explanation, url, hdurl, media_type (image|video), date, copyright.

Chave grátis (chega por email em segundos) em api.nasa.gov. Aceita DEMO_KEY
para testes (limite baixo: ~30/hora). Cuidado: o APOD às vezes é VÍDEO.

Cacheamos 1x/dia (NASA_TTL, default 6h) — a imagem só muda uma vez por dia.
Fail-open: erro → cache antigo (se houver) ou None.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.parse
import urllib.request

API_URL = "https://api.nasa.gov/planetary/apod"

_cache = {"ts": 0.0, "data": None}


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


def parse_apod(data: dict) -> dict | None:
    if not data or not data.get("title"):
        return None
    media = data.get("media_type", "image")
    # para vídeo, usa thumbnail se houver; senão marca como vídeo
    img = data.get("url", "")
    return {
        "title": data.get("title", ""),
        "explanation": (data.get("explanation", "") or "")[:300],
        "image": img if media == "image" else data.get("thumbnail_url", ""),
        "hdurl": data.get("hdurl", img),
        "media_type": media,
        "date": data.get("date", ""),
        "copyright": data.get("copyright", "NASA"),
        "page_url": img,  # link para abrir (imagem ou vídeo)
    }


def fetch_apod(api_key: str | None = None, fetch=None, timeout: int = 12,
               ttl: int | None = None) -> dict | None:
    """Foto astronômica do dia. Cacheada (muda 1x/dia). Fail-open."""
    api_key = api_key or os.getenv("NASA_API_KEY", "") or "DEMO_KEY"
    ttl = ttl if ttl is not None else int(os.getenv("NASA_TTL", "21600"))  # 6h

    if fetch is None and _cache["data"] and (time.time() - _cache["ts"]) < ttl:
        return _cache["data"]

    params = urllib.parse.urlencode({"api_key": api_key, "thumbs": "true"})
    url = f"{API_URL}?{params}"

    if fetch is not None:
        data, err = fetch(url, timeout), None
    else:
        data, err = _http_get(url, timeout)

    if err:
        print(f"[nasa] falhou: {err}")
        return _cache["data"]

    apod = parse_apod(data)
    if apod and fetch is None:
        _cache["ts"] = time.time()
        _cache["data"] = apod
    return apod
