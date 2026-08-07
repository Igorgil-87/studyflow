"""
analytics/instagram_fetcher.py — busca métrica REAL do Instagram pros
Reels que o StudyFlow publicou, e atualiza analytics/store.py.

Usa GET /{media-id}/insights (Graph API), reaproveitando as mesmas
credenciais já usadas pra publicar (tools/instagram_client.py —
IG_ACCESS_TOKEN no .env).

Métricas usadas: views, reach, likes, comments, saved, shares —
confirmadas como as atuais em 03/08/2026 (a API do Instagram descontinuou
"impressions" e "video_views" na v22.0, substituídos por "views").

IMPORTANTE — limitação da própria Instagram, não do código: métrica de
engajamento só fica disponível pra contas com 1000+ seguidores. Conta
menor que isso, a chamada pode voltar vazia ou com erro de permissão —
tratado como fail-open (sem métrica, não como erro fatal).
"""

from __future__ import annotations

import os

import requests

from tools.instagram_client import GRAPH_API_BASE, _configured, _token

_TIMEOUT = 30


class InstagramInsightsError(RuntimeError):
    """Erro ao buscar métrica do Instagram."""


def is_alive() -> bool:
    return _configured()


def fetch_metrics_for_media(media_id: str) -> dict:
    """Busca as métricas de UM Reel publicado. Retorna um dict pronto
    pra passar direto pra analytics.store.atualizar_metricas() — chaves
    que não vieram na resposta ficam de fora (fail-open parcial, mesma
    lógica do youtube_fetcher.py)."""
    if not _configured():
        raise InstagramInsightsError(
            "Instagram não configurado (IG_ACCESS_TOKEN/IG_BUSINESS_ACCOUNT_ID)."
        )

    try:
        resp = requests.get(
            f"{GRAPH_API_BASE}/{media_id}/insights",
            params={
                "metric": "views,reach,likes,comments,saved,shares",
                "access_token": _token(),
            },
            timeout=_TIMEOUT,
        )
        body = resp.json()
    except requests.RequestException as e:
        raise InstagramInsightsError(f"Falha na chamada ao Instagram: {e}") from e

    if "error" in body:
        # comum pra conta com <1000 seguidores (métrica de engajamento
        # não fica disponível) — trata como "sem métrica", não erro fatal
        msg = body["error"].get("message", str(body["error"]))
        print(f"[analytics] Instagram não devolveu insights pra {media_id}: {msg}")
        return {}

    valores = {}
    for item in body.get("data", []):
        nome = item.get("name")
        vals = item.get("values") or []
        if nome and vals:
            valores[nome] = vals[0].get("value")

    # mapeia os nomes da API do Instagram pros nomes das nossas colunas
    resultado = {}
    if "views" in valores:
        resultado["views"] = int(valores["views"])
    if "reach" in valores:
        resultado["alcance"] = int(valores["reach"])
    if "likes" in valores:
        resultado["likes"] = int(valores["likes"])
    if "comments" in valores:
        resultado["comentarios"] = int(valores["comments"])
    if "shares" in valores:
        resultado["compartilhamentos"] = int(valores["shares"])
    # "saved" (quantos salvaram) não tem coluna própria no schema hoje —
    # fica de fora por ora, dá pra adicionar depois se fizer falta.

    return resultado


def atualizar_metricas_pendentes(horas_desde_publicacao: int = 24, limit: int = 50) -> dict:
    """Mesmo padrão do youtube_fetcher.py: pega os Reels publicados que
    já têm tempo suficiente no ar e ainda não tiveram métrica buscada."""
    from analytics.store import pendentes_de_metrica, atualizar_metricas

    pendentes = [p for p in pendentes_de_metrica(horas_desde_publicacao, limit)
                 if p["plataforma"] == "instagram"]
    if not pendentes:
        return {"processadas": 0, "ok": 0, "falhas": 0, "detalhes": []}

    ok, falhas, detalhes = 0, 0, []
    for pub in pendentes:
        try:
            metricas = fetch_metrics_for_media(pub["external_id"])
            if metricas:
                atualizar_metricas(pub["id"], **metricas)
                ok += 1
                detalhes.append({"media_id": pub["external_id"], "status": "ok", **metricas})
            else:
                detalhes.append({"media_id": pub["external_id"], "status": "sem_dado"})
        except Exception as e:
            falhas += 1
            detalhes.append({"media_id": pub["external_id"], "status": "erro", "erro": str(e)})

    return {"processadas": len(pendentes), "ok": ok, "falhas": falhas, "detalhes": detalhes}
