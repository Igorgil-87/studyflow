"""rag/query.py — busca por similaridade, citações e debug verificável."""
from __future__ import annotations
from . import config


def search(query, embed_fn, store, top_k=None, video_id=None) -> list[dict]:
    if store is None or not query:
        return []
    from .hybrid import search_hibrida
    return search_hibrida(query, embed_fn, store, top_k=top_k, video_id=video_id)


def _label_for_chunk(c: dict, idx: int) -> str:
    m = c.get("metadata") or {}
    name = m.get("source_name") or c.get("video_id") or "fonte"
    if m.get("page") is not None:
        loc = f"página {m['page']}"
    elif m.get("slide") is not None:
        loc = f"slide {m['slide']}"
    elif m.get("source_type") == "video" or not str(c.get("video_id", "")).startswith("material:"):
        loc = f"{float(c.get('start') or 0):.0f}s–{float(c.get('end') or 0):.0f}s"
    else:
        loc = f"chunk {m.get('chunk_id', int(c.get('start') or 0))}"
    return f"[Fonte {idx}] {name} · {loc}"


def format_sources(chunks: list[dict]) -> list[dict]:
    out = []
    for idx, c in enumerate(chunks, start=1):
        m = c.get("metadata") or {}
        source = {
            "citation_id": idx,
            "video_id": c.get("video_id"),
            "source_name": m.get("source_name") or c.get("video_id"),
            "source_type": m.get("source_type") or ("document" if str(c.get("video_id", "")).startswith("material:") else "video"),
            "page": m.get("page"), "slide": m.get("slide"),
            "chunk_id": m.get("chunk_id", int(c.get("start") or 0)),
            "start": c.get("start"), "end": c.get("end"), "score": c.get("score"),
            "trecho": (c.get("text") or "")[:500],
            "citation": _label_for_chunk(c, idx),
        }
        out.append(source)
    return out


def build_prompt(query: str, chunks: list[dict]) -> str:
    blocks = []
    for idx, c in enumerate(chunks, start=1):
        blocks.append(f"{_label_for_chunk(c, idx)}\n{c.get('text','')}")
    ctx = "\n\n---\n\n".join(blocks)
    return (
        "Você responde USANDO SOMENTE as fontes abaixo. Se a resposta não estiver nas fontes, "
        "diga claramente que não encontrou. Cite as evidências no corpo da resposta usando "
        "[Fonte 1], [Fonte 2] etc. Não invente páginas, timestamps ou referências.\n\n"
        f"CONTEXTO:\n{ctx}\n\nPERGUNTA: {query}\n\nRESPOSTA:"
    )


def answer(query, embed_fn, store, llm_fn, top_k=None, video_id=None) -> dict:
    chunks = search(query, embed_fn, store, top_k, video_id)
    if not chunks:
        return {"answer": "Não há nada indexado sobre isso ainda. Gere/transcreva um vídeo ou envie material com o RAG ligado.",
                "sources": [], "retrieval_debug": {"top_k": top_k or config.TOP_K, "returned": 0}}
    resp = llm_fn(build_prompt(query, chunks))
    sources = format_sources(chunks)
    return {
        "answer": resp,
        "sources": sources,
        "retrieval_debug": {
            "top_k": top_k or config.TOP_K,
            "returned": len(chunks),
            "query": query,
            "filter": video_id,
            "results": [{"rank": i + 1, "score": s.get("score"), "source_name": s.get("source_name"),
                         "page": s.get("page"), "slide": s.get("slide"), "chunk_id": s.get("chunk_id")}
                        for i, s in enumerate(sources)],
        },
    }
