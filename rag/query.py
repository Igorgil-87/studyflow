"""rag/query.py — busca por similaridade e resposta ancorada (RAG)."""

from __future__ import annotations

from . import config


def search(query, embed_fn, store, top_k=None, video_id=None) -> list[dict]:
    if store is None or not query:
        return []
    qv = embed_fn(query)
    if not qv:
        return []
    return store.search(qv, top_k=top_k or config.TOP_K, video_id=video_id)


def build_prompt(query: str, chunks: list[dict]) -> str:
    ctx = "\n".join(f"[{c['start']:.0f}s] {c['text']}" for c in chunks)
    return (
        "Você responde perguntas USANDO SOMENTE o contexto abaixo — trechos de "
        "transcrição de vídeo, cada um com seu timestamp. Se a resposta não "
        "estiver no contexto, diga claramente que não encontrou. Sempre cite os "
        "timestamps que usou.\n\n"
        f"CONTEXTO:\n{ctx}\n\n"
        f"PERGUNTA: {query}\n\nRESPOSTA:"
    )


def answer(query, embed_fn, store, llm_fn, top_k=None, video_id=None) -> dict:
    """Retorna {answer, sources[]}. sources trazem timestamp e score."""
    chunks = search(query, embed_fn, store, top_k, video_id)
    if not chunks:
        return {"answer": "Não há nada indexado sobre isso ainda. "
                          "Gere/transcreva um vídeo com o RAG ligado.",
                "sources": []}
    resp = llm_fn(build_prompt(query, chunks))
    sources = [{"video_id": c.get("video_id"), "start": c["start"],
                "end": c["end"], "score": c.get("score"),
                "trecho": (c["text"] or "")[:200]} for c in chunks]
    return {"answer": resp, "sources": sources}
