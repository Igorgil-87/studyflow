"""
rag/store.py — base vetorial.

PgVectorStore: Postgres + pgvector (produção). Usa o operador de distância de
cosseno `<=>` e um índice ivfflat. As credenciais e libs são carregadas de forma
tardia, então a ausência do Postgres nunca quebra o app.

InMemoryStore: mesma interface, busca por cosseno em Python — usada nos testes e
como fallback quando o pgvector não está disponível.
"""

from __future__ import annotations

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
    """Fallback/test store: cosseno em Python."""

    def __init__(self):
        self._rows: list[dict] = []

    def add(self, items: list[dict]) -> None:
        self._rows.extend(i for i in items if i.get("embedding"))

    def search(self, qv, top_k=5, video_id=None) -> list[dict]:
        rows = [r for r in self._rows if video_id is None or r["video_id"] == video_id]
        scored = sorted(
            ((_cosine(qv, r["embedding"]), r) for r in rows),
            key=lambda x: x[0], reverse=True,
        )
        out = []
        for score, r in scored[:top_k]:
            out.append({"video_id": r["video_id"], "start": r["start"],
                        "end": r["end"], "text": r["text"], "score": round(score, 4)})
        return out

    def count(self) -> int:
        return len(self._rows)


class PgVectorStore:
    """Produção: Postgres + pgvector."""

    def __init__(self, dsn: str, dim: int = 1536, table: str = "rag_chunks"):
        import psycopg2  # import tardio
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
                "id bigserial PRIMARY KEY, video_id text, "
                "start_s double precision, end_s double precision, "
                f"text text, embedding vector({self.dim}));"
            )
            # HNSW em vez de IVFFlat: o IVFFlat "treina" os clusters no
            # momento da criação do índice — como essa CREATE INDEX roda
            # na primeira inicialização (tabela ainda VAZIA), o treino sai
            # ruim e a busca fica menos precisa pro resto da vida da
            # tabela (só se resolve recriando o índice depois de já ter
            # dado, o que ninguém costuma lembrar de fazer). HNSW constrói
            # incrementalmente, sem esse problema — é a recomendação atual
            # do próprio pgvector pra esse tipo de caso. Disponível na
            # imagem pgvector/pgvector:pg16 que já usamos.
            # Migração: se um índice ivfflat antigo com esse nome já existe
            # (bancos criados antes dessa mudança), CREATE INDEX IF NOT
            # EXISTS abaixo pularia silenciosamente sem trocar pro HNSW —
            # dropa primeiro. DROP é rápido (índice, não a tabela); CREATE
            # só roda de fato na primeira vez (depois já existe e pula).
            c.execute(f"DROP INDEX IF EXISTS ix_{self.table}_vec;")
            c.execute(
                f"CREATE INDEX IF NOT EXISTS ix_{self.table}_vec_hnsw ON {self.table} "
                "USING hnsw (embedding vector_cosine_ops);"
            )
            # Índice comum (B-tree) em video_id: toda busca filtrada por
            # vídeo/documento específico ("WHERE video_id = %s", ver
            # search() abaixo) varria a tabela inteira sem isso.
            c.execute(
                f"CREATE INDEX IF NOT EXISTS ix_{self.table}_video_id "
                f"ON {self.table} (video_id);"
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
                    "(video_id, start_s, end_s, text, embedding) "
                    "VALUES (%s,%s,%s,%s,%s::vector)",
                    (it.get("video_id"), it.get("start"), it.get("end"),
                     it.get("text"), self._vec(it["embedding"])),
                )

    def search(self, qv, top_k=5, video_id=None) -> list[dict]:
        q = self._vec(qv)
        sql = (f"SELECT video_id, start_s, end_s, text, "
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
        return [{"video_id": r[0], "start": r[1], "end": r[2],
                 "text": r[3], "score": round(float(r[4]), 4)} for r in rows]

    def count(self) -> int:
        with self.conn.cursor() as c:
            c.execute(f"SELECT count(*) FROM {self.table}")
            return c.fetchone()[0]


def get_store():
    """PgVector se RAG_ENABLED e Postgres acessível; senão None (fail-open)."""
    if not config.RAG_ENABLED:
        return None
    try:
        return PgVectorStore(config.DATABASE_URL, dim=config.EMBED_DIM,
                             table=config.TABLE)
    except Exception as e:
        print(f"[rag.store] pgvector indisponível (RAG desligado): {e}")
        return None
