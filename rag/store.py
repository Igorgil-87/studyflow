"""
rag/store.py — base vetorial com metadados de proveniência.

PgVectorStore: Postgres + pgvector (produção). Mantém compatibilidade com a
estrutura antiga de rag_chunks e adiciona metadata_json de forma aditiva.
InMemoryStore: mesma interface para testes/fallback.
"""
from __future__ import annotations

import json
import math
from . import config


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class InMemoryStore:
    def __init__(self):
        self._rows: list[dict] = []

    def add(self, items: list[dict]) -> None:
        self._rows.extend(i for i in items if i.get("embedding"))

    def search(self, qv, top_k=5, video_id=None) -> list[dict]:
        rows = [r for r in self._rows if video_id is None or r["video_id"] == video_id]
        scored = sorted(((_cosine(qv, r["embedding"]), r) for r in rows), key=lambda x: x[0], reverse=True)
        out = []
        for score, r in scored[:top_k]:
            out.append({
                "video_id": r["video_id"], "start": r["start"], "end": r["end"],
                "text": r["text"], "score": round(score, 4),
                "metadata": dict(r.get("metadata") or {}),
            })
        return out

    def search_bm25(self, query_texto: str, top_k=5, video_id=None) -> list[dict]:
        """Fallback simples (substring, case-insensitive) — sem Postgres
        não tem GIN/ts_rank de verdade, mas mantém a mesma interface
        (incluindo metadata) do search_bm25 do PgVectorStore."""
        if not query_texto or not query_texto.strip():
            return []
        termos = query_texto.lower().split()
        rows = [r for r in self._rows if video_id is None or r["video_id"] == video_id]
        scored = []
        for r in rows:
            texto_lower = (r["text"] or "").lower()
            score = sum(texto_lower.count(t) for t in termos)
            if score > 0:
                scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{
            "video_id": r["video_id"], "start": r["start"], "end": r["end"],
            "text": r["text"], "score": round(float(score), 4),
            "metadata": dict(r.get("metadata") or {}),
        } for score, r in scored[:top_k]]

    def count(self) -> int:
        return len(self._rows)


class PgVectorStore:
    def __init__(self, dsn: str, dim: int = 1536, table: str = "rag_chunks"):
        import psycopg2
        self.table = table
        self.dim = dim
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = True
        self._ensure()

    def _ensure(self) -> None:
        with self.conn.cursor() as c:
            c.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            c.execute(
                f"CREATE TABLE IF NOT EXISTS {self.table} ("
                "id bigserial PRIMARY KEY, video_id text, start_s double precision, "
                "end_s double precision, text text, "
                f"embedding vector({self.dim}), metadata_json jsonb DEFAULT '{{}}'::jsonb);"
            )
            # Migração aditiva para bancos anteriores à Sprint 2.
            c.execute(f"ALTER TABLE {self.table} ADD COLUMN IF NOT EXISTS metadata_json jsonb DEFAULT '{{}}'::jsonb;")
            c.execute(f"DROP INDEX IF EXISTS ix_{self.table}_vec;")
            c.execute(
                f"CREATE INDEX IF NOT EXISTS ix_{self.table}_vec_hnsw ON {self.table} "
                "USING hnsw (embedding vector_cosine_ops);"
            )
            c.execute(f"CREATE INDEX IF NOT EXISTS ix_{self.table}_video_id ON {self.table} (video_id);")
            # Busca híbrida (Sprint A da fusão RAG) — coluna gerada automaticamente
            # (GENERATED ALWAYS AS ... STORED, sem trigger, sempre sincronizada
            # com `text`) + índice GIN. Cobre o que a busca vetorial sozinha
            # erra: termo técnico exato, sigla, nome próprio.
            c.execute(
                f"ALTER TABLE {self.table} ADD COLUMN IF NOT EXISTS "
                f"text_search tsvector GENERATED ALWAYS AS "
                f"(to_tsvector('portuguese', coalesce(text, ''))) STORED;"
            )
            c.execute(
                f"CREATE INDEX IF NOT EXISTS ix_{self.table}_text_search "
                f"ON {self.table} USING gin (text_search);"
            )

    @staticmethod
    def _vec(v: list[float]) -> str:
        return "[" + ",".join(f"{x:.6f}" for x in v) + "]"

    def add(self, items: list[dict]) -> None:
        with self.conn.cursor() as c:
            for it in items:
                if not it.get("embedding"):
                    continue
                c.execute(
                    f"INSERT INTO {self.table} "
                    "(video_id, start_s, end_s, text, embedding, metadata_json) "
                    "VALUES (%s,%s,%s,%s,%s::vector,%s::jsonb)",
                    (it.get("video_id"), it.get("start"), it.get("end"), it.get("text"),
                     self._vec(it["embedding"]), json.dumps(it.get("metadata") or {}, ensure_ascii=False)),
                )

    def search(self, qv, top_k=5, video_id=None) -> list[dict]:
        q = self._vec(qv)
        sql = (f"SELECT video_id, start_s, end_s, text, metadata_json, "
               f"1 - (embedding <=> %s::vector) AS score FROM {self.table}")
        params: list = [q]
        if video_id:
            sql += " WHERE video_id = %s"
            params.append(video_id)
        sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
        params += [q, top_k]
        with self.conn.cursor() as c:
            c.execute(sql, params)
            rows = c.fetchall()
        return [{
            "video_id": r[0], "start": r[1], "end": r[2], "text": r[3],
            "metadata": r[4] or {}, "score": round(float(r[5]), 4),
        } for r in rows]

    def search_bm25(self, query_texto: str, top_k=5, video_id=None) -> list[dict]:
        """Busca por palavra-chave (ts_rank_cd sobre o índice GIN de
        text_search) — Sprint A da busca híbrida. Inclui metadata_json
        no retorno, mesmo formato do search() vetorial, pra não perder
        proveniência quando os dois resultados forem fundidos (RRF)."""
        if not query_texto or not query_texto.strip():
            return []
        sql = (
            f"SELECT video_id, start_s, end_s, text, metadata_json, "
            f"ts_rank_cd(text_search, plainto_tsquery('portuguese', %s)) AS score "
            f"FROM {self.table} "
            f"WHERE text_search @@ plainto_tsquery('portuguese', %s)"
        )
        params: list = [query_texto, query_texto]
        if video_id:
            sql += " AND video_id = %s"
            params.append(video_id)
        sql += " ORDER BY score DESC LIMIT %s"
        params.append(top_k)
        with self.conn.cursor() as c:
            c.execute(sql, params)
            rows = c.fetchall()
        return [{
            "video_id": r[0], "start": r[1], "end": r[2], "text": r[3],
            "metadata": r[4] or {}, "score": round(float(r[5]), 4),
        } for r in rows]

    def count(self) -> int:
        with self.conn.cursor() as c:
            c.execute(f"SELECT count(*) FROM {self.table}")
            return c.fetchone()[0]


def get_store():
    if not config.RAG_ENABLED:
        return None
    try:
        return PgVectorStore(config.DATABASE_URL, dim=config.EMBED_DIM, table=config.TABLE)
    except Exception as e:
        print(f"[rag.store] pgvector indisponível (RAG desligado): {e}")
        return None
