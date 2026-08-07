"""
cache/embeddings.py — embeddings para o cache semântico.

Usa text-embedding-3-small da OpenAI (barato: ~100x mais barato que geração).
Import tardio e tolerante: se a camada semântica estiver desligada ou a chamada
falhar, retorna None e o cache cai para modo exato (sem quebrar nada).
"""

from __future__ import annotations

import os

# Liga/desliga a camada semântica (o cache exato continua valendo).
CACHE_SEMANTIC = os.getenv("CACHE_SEMANTIC", "1") != "0"
EMBED_MODEL = os.getenv("CACHE_EMBED_MODEL", "text-embedding-3-small")
# Trunca a entrada para o embedding (o hash exato usa o texto completo).
EMBED_MAX_CHARS = int(os.getenv("CACHE_EMBED_MAX_CHARS", "8000"))

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI()
    return _client


def embed(text: str) -> list[float] | None:
    if not CACHE_SEMANTIC or not text:
        return None
    try:
        resp = _get_client().embeddings.create(
            model=EMBED_MODEL, input=text[:EMBED_MAX_CHARS]
        )
        return resp.data[0].embedding
    except Exception as e:
        print(f"[cache.embeddings] embed falhou (cache exato apenas): {e}")
        return None
