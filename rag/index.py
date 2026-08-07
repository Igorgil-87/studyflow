"""rag/index.py — indexa uma transcrição na base vetorial."""

from __future__ import annotations

from .chunker import chunk_segments, chunk_text
from . import config


def index_transcript(video_id, segments, embed_fn, store,
                     max_chars=None, max_seconds=None) -> int:
    """
    Quebra os segmentos em chunks, gera embeddings e grava na store.
    Retorna quantos chunks foram indexados. Fail-open: store=None → 0.
    """
    if store is None or not segments:
        return 0
    chunks = chunk_segments(
        segments,
        max_chars or config.CHUNK_CHARS,
        max_seconds or config.CHUNK_SECONDS,
    )
    items = []
    for ch in chunks:
        emb = embed_fn(ch["text"])
        if not emb:
            continue
        items.append({"video_id": video_id, "start": ch["start"],
                      "end": ch["end"], "text": ch["text"], "embedding": emb})
    if items:
        store.add(items)
    return len(items)


def index_document(doc_id: str, text: str, embed_fn, store,
                    max_chars: int = None) -> int:
    """Indexa um documento de material de apoio (PDF/PPTX/DOCX já
    extraído em texto puro) — SÓ usado pelo módulo Curso.

    Reaproveita a MESMA tabela/store dos vídeos (rag_chunks) — nenhuma
    migração de schema necessária. Convenção pra diferenciar na busca:
    doc_id sempre começa com "material:" (ex: "material:<uuid>"), então
    dá pra filtrar/och identificar depois sem mudar o schema. Os campos
    start/end viram o ÍNDICE do chunk (0, 1, 2...) em vez de tempo em
    segundos — só pra manter a ordem, sem timestamp real fazer sentido
    pra texto de documento.

    Fail-open: store=None ou texto vazio → 0."""
    if store is None or not text or not text.strip():
        return 0
    if not doc_id.startswith("material:"):
        raise ValueError('doc_id precisa começar com "material:" (convenção do módulo Curso)')

    chunks = chunk_text(text, max_chars or config.CHUNK_CHARS)
    items = []
    for i, chunk in enumerate(chunks):
        emb = embed_fn(chunk)
        if not emb:
            continue
        items.append({"video_id": doc_id, "start": float(i), "end": float(i),
                      "text": chunk, "embedding": emb})
    if items:
        store.add(items)
    return len(items)


def index_trends(all_results: dict, embed_fn, store) -> int:
    """
    Indexa as tendências analisadas na base vetorial. Cada trend vira um
    documento (título + insight + ângulo + hashtags), pesquisável depois no /rag.
    Fail-open: store=None → 0.
    """
    if store is None or not all_results:
        return 0
    n = 0
    for categoria, trends in all_results.items():
        for t in (trends or []):
            tags = " ".join(f"#{h}" for h in (t.get("hashtags") or []))
            text = " ".join(filter(None, [
                t.get("titulo"), t.get("insight"), t.get("angulo"), tags,
            ])).strip()
            if not text:
                continue
            emb = embed_fn(text)
            if not emb:
                continue
            store.add([{"video_id": f"trend:{categoria}", "start": 0, "end": 0,
                        "text": text, "embedding": emb}])
            n += 1
    return n
