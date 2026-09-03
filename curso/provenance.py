"""
curso/provenance.py — Fase 2 do AI Course Generation Engine (ver
ai-course-engine-diagnostico.md, seção 11). Busca os trechos REAIS do
documento original (via RAG já indexado em /api/curso2/criar) que
fundamentam uma aula, e monta a lista de claims que vira
curso/store.save_provenance().

Antes da Fase 2, o material passado pro LessonContentAgent era só a
descrição do curso + objetivo/conceitos do manifest — nunca voltava no
documento original. Agora, quando o curso tem source_doc_id (Modo
Criativo), busca de verdade os chunks mais relevantes pra cada aula.
"""

from __future__ import annotations

MIN_SCORE_FONTE = 0.15  # abaixo disso, chunk não é considerado fundamentação


def buscar_chunks_relevantes(source_doc_id: str, query_texto: str, top_k: int = 5) -> list[dict]:
    """Busca no RAG os chunks do documento original mais relevantes pra
    esta aula (concatena título+objetivo+conceitos como query). Fail-open:
    RAG desligado/indisponível -> lista vazia (a aula ainda gera, só sem
    fundamentação real do documento — vira 'complementar')."""
    if not source_doc_id or not query_texto:
        return []
    try:
        from cache.embeddings import embed
        from rag.query import search
        from rag.store import get_store

        store = get_store()
        if store is None:
            return []
        return search(query_texto, embed, store, top_k=top_k, video_id=source_doc_id)
    except Exception as e:
        print(f"[provenance] busca no RAG falhou (aula segue sem fundamentação real): {e}")
        return []


def montar_material_e_claims(
    source_doc_id: str, titulo_aula: str, objetivo: str, conceitos: list[str],
    contexto_fallback: str,
) -> tuple[str, list[dict]]:
    """Retorna (material_pra_gerar_conteudo, claims_de_provenance).

    Se achar chunks reais do documento: material = chunks concatenados,
    claims marcadas tipo='fonte' (com chunk_id = índice do chunk no
    documento — não é página real, ver rag/index.index_document).

    Se não achar nada (RAG desligado, curso veio do YouTube, ou material
    não indexado): cai pro contexto do manifest (comportamento da Fase 1),
    e a claim única fica marcada tipo='complementar' — deixa explícito
    pro usuário que aquele conteúdo não tem fundamentação rastreável no
    documento original (regra do pedido: nunca misturar SOURCE MATERIAL
    com AI COMPLEMENTARY CONTENT silenciosamente)."""
    query_texto = f"{titulo_aula}. {objetivo}. {', '.join(conceitos)}"
    chunks = buscar_chunks_relevantes(source_doc_id, query_texto) if source_doc_id else []

    if chunks:
        material = "\n\n---\n\n".join(c["text"] for c in chunks)
        claims = []
        for c in chunks:
            meta = c.get("metadata") or {}
            claims.append({
                "claim_text": c["text"][:500],
                "tipo": "fonte",
                "doc_id": source_doc_id,
                "chunk_id": str(meta.get("chunk_id", c.get("start", ""))),
                "page": meta.get("page"),
                "section": meta.get("section") or (f"Slide {meta.get('slide')}" if meta.get("slide") is not None else None),
                "source_name": meta.get("source_name"),
                "score": c.get("score"),
            })
        return material, claims

    claims = [{
        "claim_text": contexto_fallback[:500],
        "tipo": "complementar",
        "doc_id": None, "chunk_id": None, "page": None, "section": None,
    }]
    return contexto_fallback, claims
