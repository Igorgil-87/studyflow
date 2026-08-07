"""
cache/ttl_cache.py — cache exato com expiração (TTL).

Diferente do cache semântico (que casa por similaridade), aqui a chave é exata
e o valor expira sozinho. Ideal para as tendências: o mesmo nicho/categoria
dentro da janela (ex.: 1h) reaproveita o resultado e ECONOMIZA as chamadas de
IA (que são caras — multi-LLM).

Tudo fail-open: qualquer erro de I/O retorna None e o chamador segue chamando a
IA normalmente.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time

DB = os.getenv("TTL_CACHE_DB", "output/ttl_cache.db")


def _conn():
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    con = sqlite3.connect(DB, timeout=5)
    con.execute(
        "CREATE TABLE IF NOT EXISTS ttl ("
        "key TEXT PRIMARY KEY, value TEXT, expires_at REAL)"
    )
    return con


def get(key: str):
    try:
        con = _conn()
        row = con.execute(
            "SELECT value, expires_at FROM ttl WHERE key=?", (key,)
        ).fetchone()
        if not row:
            con.close()
            return None
        value, expires_at = row
        if expires_at < time.time():            # expirou → remove e ignora
            con.execute("DELETE FROM ttl WHERE key=?", (key,))
            con.commit()
            con.close()
            return None
        con.close()
        return json.loads(value)
    except Exception as e:
        print(f"[ttl_cache] get falhou (seguindo): {e}")
        return None


def set(key: str, value, ttl_seconds: float) -> None:
    try:
        con = _conn()
        con.execute(
            "INSERT OR REPLACE INTO ttl (key, value, expires_at) VALUES (?,?,?)",
            (key, json.dumps(value, ensure_ascii=False), time.time() + ttl_seconds),
        )
        con.commit()
        con.close()
    except Exception as e:
        print(f"[ttl_cache] set falhou (seguindo): {e}")


def ttl_left(key: str) -> float:
    """Segundos restantes para a chave (0 se ausente/expirada)."""
    try:
        con = _conn()
        row = con.execute(
            "SELECT expires_at FROM ttl WHERE key=?", (key,)
        ).fetchone()
        con.close()
        if not row:
            return 0.0
        return max(0.0, row[0] - time.time())
    except Exception:
        return 0.0
