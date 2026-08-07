"""
tools/rag_context.py — busca contexto relevante na base vetorial (RAG) do
projeto (vídeos transcritos + tendências indexadas) pra alimentar o texto
do carrossel com informação real do seu conteúdo, em vez de só
conhecimento genérico do LLM.

Fail-open sempre: RAG desligado, Postgres indisponível, ou zero resultados
relevantes → retorna string vazia, e o resto do pipeline segue normal
(sem contexto extra, exatamente como era antes).

Embeddings continuam via OpenAI (text-embedding-3-small) — a Anthropic
não tem API própria de embeddings, então trocar isso exigiria reindexar
tudo com outro provedor (ex: Voyage AI) e mudar RAG_EMBED_DIM. O TEXTO
gerado a partir desse contexto, porém, pode ser qualquer LLM — é só o
llm_fn que muda (ver claude_copy_client.py, que já é Claude)."""

from __future__ import annotations


def get_context_for_topic(topic: str, *, top_k: int = 5) -> str:
    """Retorna um bloco de texto com os trechos mais relevantes já
    indexados (vídeos + tendências) sobre o tema, prontos pra colar no
    prompt de outro LLM. String vazia se não houver nada relevante ou o
    RAG estiver desligado."""
    if not topic:
        return ""
    try:
        from rag.store import get_store
        from rag.query import search
        from cache.embeddings import embed
    except ImportError:
        return ""

    try:
        store = get_store()
        if store is None:
            return ""
        chunks = search(topic, embed, store, top_k=top_k)
    except Exception as e:
        print(f"[tools.rag_context] busca falhou (seguindo sem contexto): {e}")
        return ""

    if not chunks:
        return ""

    parts = []
    for c in chunks:
        origem = c.get("video_id") or "conteúdo indexado"
        parts.append(f"- ({origem}) {(c.get('text') or '').strip()}")
    return "\n".join(parts)
