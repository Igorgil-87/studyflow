"""rag/config.py — configuração do RAG (pgvector)."""

import os

RAG_ENABLED = os.getenv("RAG_ENABLED", "0") != "0"
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://studyflow:studyflow@localhost:5432/studyflow"
)
EMBED_DIM = int(os.getenv("RAG_EMBED_DIM", "1536"))   # text-embedding-3-small
TOP_K = int(os.getenv("RAG_TOP_K", "5"))
CHUNK_CHARS = int(os.getenv("RAG_CHUNK_CHARS", "600"))
CHUNK_SECONDS = int(os.getenv("RAG_CHUNK_SECONDS", "60"))
TABLE = os.getenv("RAG_TABLE", "rag_chunks")
