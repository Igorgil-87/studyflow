"""
tools/topic_video_finder.py — busca vídeos sobre um ASSUNTO e garante relevância.

Problema: a busca por palavra-chave do YouTube traz muito vídeo fora do tema.
Solução: depois de buscar candidatos, um LLM LÊ título/canal/descrição de cada um
e decide se é REALMENTE sobre o assunto (ex.: "política" → só política mesmo),
descartando o que não for e ranqueando por relevância.

Tudo é injetável (`search_fn`, `llm_fn`) para testar sem rede nem credencial.
Fail-open: se o LLM falhar, devolve os resultados crus em vez de nada.
"""

from __future__ import annotations

import json


def _parse_videos(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return data if isinstance(data, list) else []


def _parse_judgments(raw: str) -> list[dict]:
    if not raw:
        return []
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return []
    return data if isinstance(data, list) else []


def build_query(topic: str, niche: str) -> str:
    topic = (topic or "").strip()
    niche = (niche or "").strip()
    if not niche or niche.lower() in topic.lower():
        return topic
    return f"{topic} {niche}".strip()


def build_relevance_prompt(topic: str, niche: str, videos: list[dict]) -> str:
    listing = "\n".join(
        f"{i}. título: {v.get('titulo','')} | canal: {v.get('canal','')} | "
        f"descrição: {(v.get('descricao','') or '')[:160]}"
        for i, v in enumerate(videos)
    )
    return (
        "Você filtra vídeos do YouTube por RELEVÂNCIA a um assunto.\n\n"
        f'Assunto desejado: "{topic}"  (nicho: "{niche}")\n\n'
        "Para CADA vídeo abaixo, decida se ele é REALMENTE sobre esse assunto. "
        "Seja rigoroso: um vídeo de outro tema que só cita a palavra NÃO conta. "
        'Exemplo: se o assunto é "política", só valem vídeos de política — '
        "descarte música, entretenimento, esportes, etc.\n\n"
        'Responda APENAS um JSON (sem markdown), no formato:\n'
        '[{"i":0,"relevante":true,"score":0.0,"motivo":"curto"}]\n\n'
        f"VÍDEOS:\n{listing}"
    )


def find_relevant_videos(
    topic: str,
    niche: str,
    search_fn,
    llm_fn=None,
    max_candidates: int = 15,
    max_results: int = 8,
) -> dict:
    """
    Retorna {"videos": [...], "filtered": bool, "reason": str?}.

    search_fn(query, n) -> str (JSON do YouTubeSearchTool).
    llm_fn(prompt) -> str (texto do LLM). Se None, não filtra (degrade).
    """
    query = build_query(topic, niche)
    videos = _parse_videos(search_fn(query, max_candidates))
    if not videos:
        return {"videos": [], "filtered": False, "reason": "Nenhum vídeo encontrado."}

    if llm_fn is None:
        return {"videos": videos[:max_results], "filtered": False}

    judgments = _parse_judgments(llm_fn(build_relevance_prompt(topic, niche, videos)))
    if not judgments:
        # fail-open: LLM indisponível → entrega crus, sem travar o usuário
        return {"videos": videos[:max_results], "filtered": False}

    by_i = {j["i"]: j for j in judgments if isinstance(j.get("i"), int)}
    relevant = []
    for i, v in enumerate(videos):
        j = by_i.get(i)
        if j and j.get("relevante"):
            item = dict(v)
            item["relevancia"] = round(float(j.get("score", 0) or 0), 2)
            item["motivo"] = str(j.get("motivo", ""))[:200]
            relevant.append(item)

    relevant.sort(key=lambda x: x.get("relevancia", 0), reverse=True)

    if not relevant:
        return {
            "videos": [], "filtered": True,
            "reason": f'Nenhum vídeo claramente sobre "{topic}". '
                      "Tente um termo mais específico.",
        }
    return {"videos": relevant[:max_results], "filtered": True}
