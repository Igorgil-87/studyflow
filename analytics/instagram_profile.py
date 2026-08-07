"""
analytics/instagram_profile.py — puxa o HISTÓRICO COMPLETO do perfil do
Instagram (todos os posts que já existem na conta, não só os que o
StudyFlow publicou) e sincroniza com analytics/store.py. É a base do
Growth: pra achar padrão de "por que alguns posts viralizam mais",
precisa olhar o perfil inteiro, não só a dúzia de clips que passaram
pelo pipeline.

Usa a mesma credencial já configurada pra publicar (IG_ACCESS_TOKEN).
"""

from __future__ import annotations

import requests

from tools.instagram_client import GRAPH_API_BASE, _account_id, _configured, _token

_TIMEOUT = 30
_MEDIA_FIELDS = "id,caption,media_type,media_product_type,timestamp,permalink"


class InstagramProfileError(RuntimeError):
    """Erro ao sincronizar o perfil do Instagram."""


def is_alive() -> bool:
    return _configured()


def list_account_media(limit_total: int = 200) -> list[dict]:
    """Lista os posts REAIS da conta (paginado, segue o cursor 'next' da
    API até acabar ou bater o limite). Retorna os campos crus da API —
    id, caption, media_type, timestamp, permalink."""
    if not _configured():
        raise InstagramProfileError(
            "Instagram não configurado (IG_ACCESS_TOKEN/IG_BUSINESS_ACCOUNT_ID)."
        )

    items: list[dict] = []
    url = f"{GRAPH_API_BASE}/{_account_id()}/media"
    params = {"fields": _MEDIA_FIELDS, "access_token": _token(), "limit": 50}

    while url and len(items) < limit_total:
        try:
            resp = requests.get(url, params=params, timeout=_TIMEOUT)
            body = resp.json()
        except requests.RequestException as e:
            raise InstagramProfileError(f"Falha na chamada ao Instagram: {e}") from e

        if "error" in body:
            raise InstagramProfileError(body["error"].get("message", str(body["error"])))

        items.extend(body.get("data", []))

        next_url = (body.get("paging") or {}).get("next")
        url = next_url
        params = None  # a URL de 'next' já vem com todos os parâmetros embutidos

    return items[:limit_total]


def sincronizar_perfil_completo(limit_total: int = 200) -> dict:
    """Puxa o histórico completo da conta, registra cada post que ainda
    não existe no banco (origem='historico'), e busca a métrica real de
    cada um. Idempotente — rodar de novo só atualiza métrica, não duplica
    (mesmo mecanismo de UNIQUE INDEX plataforma+external_id do Sprint 1).

    Retorna um resumo: quantos posts encontrados, quantos novos, quantos
    tiveram métrica atualizada, quantas falhas."""
    from analytics.store import registrar_publicacao, atualizar_metricas
    from analytics.instagram_fetcher import fetch_metrics_for_media

    posts = list_account_media(limit_total)

    novos, com_metrica, falhas = 0, 0, 0
    detalhes = []

    for post in posts:
        media_id = post.get("id")
        if not media_id:
            continue

        try:
            registrar_publicacao(
                "instagram", media_id,
                url=post.get("permalink", ""),
                modulo="youtuber",
                titulo=(post.get("caption") or "")[:120],
                caption=post.get("caption") or "",
                origem="historico",
                publicado_em=post.get("timestamp"),
            )
            novos += 1
        except Exception as e:
            falhas += 1
            detalhes.append({"media_id": media_id, "status": "erro_registro", "erro": str(e)})
            continue

        try:
            metricas = fetch_metrics_for_media(media_id)
            if metricas:
                from analytics.store import list_publicacoes
                achado = [p for p in list_publicacoes(plataforma="instagram", limit=1000)
                          if p["external_id"] == media_id]
                if achado:
                    atualizar_metricas(achado[0]["id"], **metricas)
                    com_metrica += 1
        except Exception as e:
            detalhes.append({"media_id": media_id, "status": "sem_metrica", "erro": str(e)})

    return {
        "encontrados": len(posts), "novos_ou_atualizados": novos,
        "com_metrica": com_metrica, "falhas": falhas, "detalhes": detalhes,
    }
