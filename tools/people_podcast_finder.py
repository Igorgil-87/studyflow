"""
tools/people_podcast_finder.py — busca por PESSOA e preferência por PODCAST/ENTREVISTA.

Para cortes, conteúdo de entrevista/podcast com gente conhecida costuma render
muito mais. Este módulo:
  - monta queries focadas em podcast/entrevista (e no nome da pessoa);
  - pontua cada vídeo dando peso a sinais de podcast e à presença da pessoa;
  - ranqueia e devolve os melhores.

Tudo injetável (search_fn, llm_fn) para testar sem rede nem credencial.
"""

from __future__ import annotations

import json

# sinais de que o vídeo é entrevista/podcast (no título)
_PODCAST_HINTS = (
    "podcast", "entrevista", "entrevistou", "conversa", "papo", "bate-papo",
    "talk", "cast", "episódio", "episodio", "ep.", "#", "flow", "inteligência ltda",
    "pod", "live", "debate", "mesa", "convidado",
)


def _parse_videos(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(data, dict) and data.get("erro"):
        return []
    return data if isinstance(data, list) else []


def build_queries(person: str, topic: str = "", prefer_podcast: bool = True) -> list[str]:
    """Monta as buscas. Foca na pessoa e/ou no assunto, com viés de podcast."""
    person = (person or "").strip()
    topic = (topic or "").strip()
    queries: list[str] = []

    if person:
        if prefer_podcast:
            queries += [f"{person} podcast", f"{person} entrevista"]
        if topic:
            queries.append(f"{person} {topic}")
        queries.append(person)
    elif topic:
        if prefer_podcast:
            queries += [f"{topic} podcast", f"{topic} entrevista"]
        queries.append(topic)

    # remove duplicatas preservando ordem
    seen, out = set(), []
    for q in queries:
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out


def is_podcast_like(title: str) -> bool:
    t = (title or "").lower()
    return any(h in t for h in _PODCAST_HINTS)


def person_match(video: dict, person: str) -> bool:
    if not person:
        return False
    p = person.lower().strip()
    hay = f"{video.get('titulo', '')} {video.get('canal', '')}".lower()
    # nome completo presente
    if p in hay:
        return True
    parts = [x for x in p.split() if len(x) > 2]
    if len(parts) >= 2:
        # primeiro + último nome presentes
        if parts[0] in hay and parts[-1] in hay:
            return True
        # sobrenome distintivo sozinho (ex.: "Karnal")
        if len(parts[-1]) > 4 and parts[-1] in hay:
            return True
    return False


def score_video(video: dict, person: str = "", prefer_podcast: bool = True) -> float:
    """Pontua de 0 a ~1.2: base + podcast + pessoa + duração longa."""
    score = 0.4
    if prefer_podcast and is_podcast_like(video.get("titulo", "")):
        score += 0.30
    if person and person_match(video, person):
        score += 0.30
    dur = float(video.get("duracao_minutos", 0) or 0)
    if dur >= 20:            # podcasts/entrevistas costumam ser longos
        score += 0.15
    elif dur >= 8:
        score += 0.05
    return round(score, 3)


def _reason(video: dict, person: str, prefer_podcast: bool) -> str:
    bits = []
    if person and person_match(video, person):
        bits.append(f"menciona {person}")
    if prefer_podcast and is_podcast_like(video.get("titulo", "")):
        bits.append("formato podcast/entrevista")
    dur = float(video.get("duracao_minutos", 0) or 0)
    if dur >= 20:
        bits.append(f"{dur:.0f} min (bom p/ cortes)")
    return ", ".join(bits) or "relacionado à busca"


def find_people_videos(person: str, topic: str, search_fn, llm_fn=None,
                       prefer_podcast: bool = True, max_results: int = 8,
                       max_candidates: int = 10) -> dict:
    """
    search_fn(query, n) -> str (JSON do YouTubeSearchTool, suffix="").
    llm_fn opcional: não obrigatório (a pontuação heurística já ranqueia).
    Retorna {"videos": [...], "reason": str}.
    """
    queries = build_queries(person, topic, prefer_podcast)
    if not queries:
        return {"videos": [], "reason": "Informe uma pessoa ou um assunto."}

    seen: dict[str, dict] = {}
    for q in queries:
        for v in _parse_videos(search_fn(q, max_candidates)):
            url = v.get("url")
            if url and url not in seen:
                seen[url] = v

    videos = list(seen.values())
    if not videos:
        return {"videos": [], "reason": "Nenhum vídeo encontrado para essa busca."}

    for v in videos:
        v["_score"] = score_video(v, person, prefer_podcast)
    videos.sort(key=lambda v: v.get("_score", 0), reverse=True)

    top = videos[:max_results]
    for v in top:
        v["relevancia"] = round(min(1.0, v.get("_score", 0)), 2)
        v["motivo"] = _reason(v, person, prefer_podcast)
        v.pop("_score", None)
    return {"videos": top, "reason": ""}
