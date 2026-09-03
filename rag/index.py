"""rag/index.py — indexação vetorial com proveniência por chunk."""
from __future__ import annotations

from .chunker import chunk_segments, chunk_text
from . import config


def index_transcript(video_id, segments, embed_fn, store, max_chars=None, max_seconds=None) -> int:
    if store is None or not segments:
        return 0
    chunks = chunk_segments(segments, max_chars or config.CHUNK_CHARS, max_seconds or config.CHUNK_SECONDS)
    items = []
    for i, ch in enumerate(chunks):
        emb = embed_fn(ch["text"])
        if not emb:
            continue
        items.append({
            "video_id": video_id, "start": ch["start"], "end": ch["end"], "text": ch["text"],
            "embedding": emb,
            "metadata": {"source_type": "video", "chunk_id": i, "timestamp_start": ch["start"], "timestamp_end": ch["end"]},
        })
    if items:
        store.add(items)
    return len(items)


def index_document(doc_id: str, text: str, embed_fn, store, max_chars: int = None,
                   source_name: str | None = None, source_type: str = "document",
                   units: list[dict] | None = None) -> int:
    """Indexa documento preservando nome da fonte, página/slide e chunk.

    `units` é opcional e tem formato [{"text": ..., "page": 1}] ou
    [{"text": ..., "slide": 2}]. Sem units, mantém o comportamento antigo.
    """
    if store is None or not text or not text.strip():
        return 0
    if not doc_id.startswith("material:"):
        raise ValueError('doc_id precisa começar com "material:" (convenção do módulo Curso)')

    items = []
    global_chunk = 0
    source_name = source_name or doc_id.replace("material:", "", 1)
    source_units = units or [{"text": text}]
    for unit in source_units:
        unit_text = (unit.get("text") or "").strip()
        if not unit_text:
            continue
        for local_chunk, chunk in enumerate(chunk_text(unit_text, max_chars or config.CHUNK_CHARS)):
            emb = embed_fn(chunk)
            if not emb:
                continue
            metadata = {
                "source_type": source_type,
                "source_name": source_name,
                "chunk_id": global_chunk,
                "unit_chunk": local_chunk,
            }
            for key in ("page", "slide", "section", "url"):
                if unit.get(key) is not None:
                    metadata[key] = unit.get(key)
            items.append({
                "video_id": doc_id, "start": float(global_chunk), "end": float(global_chunk),
                "text": chunk, "embedding": emb, "metadata": metadata,
            })
            global_chunk += 1
    if items:
        store.add(items)
    return len(items)


def index_trends(all_results: dict, embed_fn, store) -> int:
    if store is None or not all_results:
        return 0
    items = []
    idx = 0
    for fonte, trends in all_results.items():
        for t in trends or []:
            if not isinstance(t, dict):
                continue
            text = "\n".join(str(t.get(k) or "") for k in ("title", "titulo", "insight", "angle", "angulo", "hashtags")).strip()
            if not text:
                continue
            emb = embed_fn(text)
            if not emb:
                continue
            items.append({"video_id": f"trend:{fonte}", "start": float(idx), "end": float(idx), "text": text,
                          "embedding": emb, "metadata": {"source_type": "trend", "source_name": fonte, "chunk_id": idx}})
            idx += 1
    if items:
        store.add(items)
    return len(items)
