"""
cache/store.py — armazenamento do cache (SQLite, mesmo arquivo do obs).

Guarda, por namespace (= operação), o hash da entrada, o embedding (opcional,
JSON), o payload do resultado e metadados. Busca exata por hash e busca
semântica por cosseno (varredura O(n) na namespace — suficiente para um cache
de tamanho modesto; em produção isso migra para pgvector/Qdrant).
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import time
from pathlib import Path

OBS_DB = os.getenv("OBS_DB", "output/observability.db")

try:
    import numpy as _np
except Exception:
    _np = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_cache (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    namespace      TEXT NOT NULL,
    input_hash     TEXT NOT NULL,
    embedding      TEXT,
    result_kind    TEXT NOT NULL,
    result_payload TEXT NOT NULL,
    file_ext       TEXT,
    created_at     REAL,
    hits           INTEGER DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_cache_ns_hash
ON llm_cache (namespace, input_hash);
CREATE INDEX IF NOT EXISTS ix_cache_ns ON llm_cache (namespace);
"""


def _connect() -> sqlite3.Connection:
    Path(OBS_DB).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(OBS_DB, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init() -> None:
    try:
        conn = _connect()
        conn.executescript(_SCHEMA)
        conn.commit()
        conn.close()
    except Exception as e:  # pragma: no cover
        print(f"[cache.store] init falhou (seguindo sem cache): {e}")


def get_exact(namespace: str, input_hash: str) -> dict | None:
    try:
        conn = _connect()
        row = conn.execute(
            "SELECT * FROM llm_cache WHERE namespace=? AND input_hash=?",
            (namespace, input_hash),
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        print(f"[cache.store] get_exact falhou: {e}")
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    if _np is not None:
        va, vb = _np.asarray(a, dtype=float), _np.asarray(b, dtype=float)
        na, nb = _np.linalg.norm(va), _np.linalg.norm(vb)
        return float(va.dot(vb) / (na * nb)) if na and nb else 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def search_semantic(namespace: str, embedding: list[float],
                    threshold: float) -> dict | None:
    """Melhor candidato da namespace com cosseno >= threshold, ou None."""
    try:
        conn = _connect()
        rows = conn.execute(
            "SELECT * FROM llm_cache WHERE namespace=? AND embedding IS NOT NULL",
            (namespace,),
        ).fetchall()
        conn.close()
    except Exception as e:
        print(f"[cache.store] search_semantic falhou: {e}")
        return None

    best, best_sim = None, 0.0
    for row in rows:
        try:
            emb = json.loads(row["embedding"])
        except Exception:
            continue
        sim = _cosine(embedding, emb)
        if sim > best_sim:
            best, best_sim = row, sim
    if best is not None and best_sim >= threshold:
        out = dict(best)
        out["similarity"] = round(best_sim, 4)
        return out
    return None


def put(namespace: str, input_hash: str, embedding: list[float] | None,
        result_kind: str, result_payload: str, file_ext: str | None) -> None:
    try:
        conn = _connect()
        conn.execute(
            """INSERT OR REPLACE INTO llm_cache
               (namespace, input_hash, embedding, result_kind, result_payload,
                file_ext, created_at, hits)
               VALUES (?,?,?,?,?,?,?,0)""",
            (namespace, input_hash,
             json.dumps(embedding) if embedding is not None else None,
             result_kind, result_payload, file_ext, time.time()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[cache.store] put falhou: {e}")


def incr_hits(entry_id: int) -> None:
    try:
        conn = _connect()
        conn.execute("UPDATE llm_cache SET hits = hits + 1 WHERE id=?", (entry_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[cache.store] incr_hits falhou: {e}")


def stats() -> dict:
    try:
        conn = _connect()
        n = conn.execute("SELECT COUNT(*) c FROM llm_cache").fetchone()["c"]
        h = conn.execute("SELECT COALESCE(SUM(hits),0) s FROM llm_cache").fetchone()["s"]
        conn.close()
        return {"entries": n, "total_hits": h}
    except Exception:
        return {"entries": 0, "total_hits": 0}
