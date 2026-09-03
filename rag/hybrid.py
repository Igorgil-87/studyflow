"""
rag/hybrid.py — Reciprocal Rank Fusion (Sprint A2 da busca híbrida).

Combina o ranking da busca vetorial (semântica, pega significado) com
o da busca por palavra-chave (search_bm25, pega termo técnico exato,
sigla, nome próprio — o que a busca vetorial sozinha às vezes erra).

Referência: mesma fórmula usada pelo OpenJarvis (Stanford, framework de
IA local-first) — `RRF_score(d) = soma(peso_i / (k + posição_i(d)))`,
técnica clássica de recuperação de informação, não é exclusividade de
ninguém. k=60 é o valor padrão da literatura (Cormack et al. 2009).
"""

from __future__ import annotations

K_PADRAO = 60


def _chave_chunk(chunk: dict) -> tuple:
    """Identifica um chunk de forma estável entre as duas buscas —
    (video_id, start) é único o bastante pra não colidir chunks
    diferentes com texto parecido."""
    return (chunk.get("video_id"), chunk.get("start"))


def reciprocal_rank_fusion(
    listas_rankeadas: list[list[dict]], *, k: int = K_PADRAO,
    pesos: list[float] | None = None,
) -> list[dict]:
    """Funde N listas já ordenadas (melhor primeiro) numa só, por RRF.
    Cada dict de entrada precisa ter video_id/start (usados como chave
    de identidade) — o resto dos campos do PRIMEIRO chunk visto pra
    cada chave é preservado no resultado, só o campo 'score' é
    substituído pelo score fundido."""
    if pesos is None:
        pesos = [1.0] * len(listas_rankeadas)

    scores_fundidos: dict[tuple, float] = {}
    melhor_chunk: dict[tuple, dict] = {}

    for peso, lista in zip(pesos, listas_rankeadas):
        for posicao, chunk in enumerate(lista):
            chave = _chave_chunk(chunk)
            rrf = peso / (k + posicao + 1)
            scores_fundidos[chave] = scores_fundidos.get(chave, 0.0) + rrf
            if chave not in melhor_chunk:
                melhor_chunk[chave] = chunk

    fundidos = []
    for chave, score in sorted(scores_fundidos.items(), key=lambda x: x[1], reverse=True):
        original = melhor_chunk[chave]
        fundidos.append({**original, "score": round(score, 6)})
    return fundidos


def search_hibrida(query_texto: str, embed_fn, store, top_k=None, video_id=None) -> list[dict]:
    """Busca híbrida de verdade: roda vetorial + palavra-chave em
    paralelo (busca mais candidatos que top_k em cada uma, pra dar
    material pra fusão escolher os melhores) e funde por RRF. Se a
    store não tiver search_bm25 (versão antiga/mock em teste antigo),
    cai pra busca vetorial pura — nunca quebra quem não migrou ainda."""
    from . import config

    limite = top_k or config.TOP_K
    candidatos_por_busca = max(limite * 3, 10)  # margem pra fusão ter o que escolher

    qv = embed_fn(query_texto) if query_texto else None
    resultado_vetorial = store.search(qv, top_k=candidatos_por_busca, video_id=video_id) if qv else []

    if not hasattr(store, "search_bm25"):
        return resultado_vetorial[:limite]

    resultado_bm25 = store.search_bm25(query_texto, top_k=candidatos_por_busca, video_id=video_id)

    if not resultado_vetorial and not resultado_bm25:
        return []

    fundidos = reciprocal_rank_fusion([resultado_vetorial, resultado_bm25])
    return fundidos[:limite]
