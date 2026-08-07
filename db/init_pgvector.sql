-- Inicialização da base vetorial (executado pelo Postgres no primeiro boot).
-- O app também garante isso em runtime (rag/store.py::_ensure), então é opcional.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rag_chunks (
    id        bigserial PRIMARY KEY,
    video_id  text,
    start_s   double precision,
    end_s     double precision,
    text      text,
    embedding vector(1536)
);

CREATE INDEX IF NOT EXISTS ix_rag_chunks_vec
    ON rag_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
