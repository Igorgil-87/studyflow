"""
analytics/youtube_fetcher.py — busca métrica REAL do YouTube pros vídeos
que o StudyFlow publicou, e atualiza analytics/store.py (fecha o loop
previsão-da-IA vs resultado-de-verdade).

Usa DUAS APIs do Google, com credenciais que já existem no projeto
(publish/auth.py — mesmo token usado pra publicar vídeo):
  - YouTube Data API v3: views/likes/comentários (dado simples, direto,
    disponível na hora, sem atraso de processamento).
  - YouTube Analytics API v2: watch time e retenção média (métrica mais
    "fina", pode levar algumas horas pra aparecer depois da publicação —
    por isso o registrar_publicacao() só busca vídeos com 24h+ no ar,
    ver analytics/store.py:pendentes_de_metrica()).

IMPORTANTE: pra isso funcionar, o token do YouTube precisa ter sido
gerado DEPOIS do escopo yt-analytics.readonly ter sido adicionado em
publish/config.py — se o token é de antes disso, reautorize:
    python3 -m publish.auth
"""

from __future__ import annotations

import datetime
import os


class YoutubeAnalyticsError(RuntimeError):
    """Erro ao buscar métrica do YouTube."""


def _build_data_service():
    from googleapiclient.discovery import build
    from publish.auth import get_credentials
    return build("youtube", "v3", credentials=get_credentials())


def _build_analytics_service():
    from googleapiclient.discovery import build
    from publish.auth import get_credentials
    return build("youtubeAnalytics", "v2", credentials=get_credentials())


def _fetch_statistics(video_id: str, service=None) -> dict:
    """Views/likes/comentários — YouTube Data API, disponível na hora."""
    service = service or _build_data_service()
    resp = service.videos().list(part="statistics", id=video_id).execute()
    items = resp.get("items", [])
    if not items:
        raise YoutubeAnalyticsError(f"Vídeo {video_id} não encontrado (foi removido/privado?)")
    stats = items[0]["statistics"]
    return {
        "views": int(stats.get("viewCount", 0)),
        "likes": int(stats.get("likeCount", 0)) if "likeCount" in stats else None,
        "comentarios": int(stats.get("commentCount", 0)) if "commentCount" in stats else None,
    }


def _fetch_watch_metrics(video_id: str, published_at_iso: str, service=None) -> dict:
    """Watch time + retenção — YouTube Analytics API. Pode não ter dado
    ainda se o vídeo é muito recente ou teve pouquíssimas visualizações
    (o YouTube não expõe métrica com volume baixo demais, por privacidade
    de quem assistiu) — nesse caso volta tudo None, sem erro."""
    service = service or _build_analytics_service()

    try:
        published_date = published_at_iso[:10]  # "YYYY-MM-DDTHH:MM:SS..." -> "YYYY-MM-DD"
    except Exception:
        published_date = "2020-01-01"
    today = datetime.date.today().isoformat()

    try:
        resp = service.reports().query(
            ids="channel==MINE",
            startDate=published_date,
            endDate=today,
            metrics="estimatedMinutesWatched,averageViewPercentage",
            filters=f"video=={video_id}",
        ).execute()
    except Exception as e:
        # comum pra vídeo recente/com pouco dado — não é erro fatal,
        # só significa "sem métrica fina ainda"
        print(f"[analytics] Sem dado de watch time pra {video_id} ainda: {e}")
        return {"watch_time_min": None, "retencao_media_pct": None}

    rows = resp.get("rows") or []
    if not rows:
        return {"watch_time_min": None, "retencao_media_pct": None}

    watch_time_min, retencao_pct = rows[0]
    return {
        "watch_time_min": float(watch_time_min),
        "retencao_media_pct": float(retencao_pct),
    }


def fetch_metrics_for_video(video_id: str, published_at_iso: str) -> dict:
    """Busca tudo (statistics + watch metrics) pra UM vídeo. Retorna um
    dict pronto pra passar direto pra analytics.store.atualizar_metricas().
    Fail-open parcial: se uma das duas partes falhar, a outra ainda
    retorna — melhor ter views sem retenção do que não ter nada."""
    resultado: dict = {}

    try:
        resultado.update(_fetch_statistics(video_id))
    except Exception as e:
        print(f"[analytics] Falha ao buscar statistics de {video_id}: {e}")

    try:
        resultado.update(_fetch_watch_metrics(video_id, published_at_iso))
    except Exception as e:
        print(f"[analytics] Falha ao buscar watch metrics de {video_id}: {e}")

    return resultado


def atualizar_metricas_pendentes(horas_desde_publicacao: int = 24, limit: int = 50) -> dict:
    """Roda em lote: pega as publicações do YouTube que já têm tempo
    suficiente no ar e ainda não tiveram métrica buscada, busca real, e
    grava. Retorna um resumo (quantas ok, quantas falharam) — pensado
    pra virar botão manual em Observabilidade agora, e tarefa agendada
    (scheduler.py) depois."""
    from analytics.store import pendentes_de_metrica, atualizar_metricas

    pendentes = [p for p in pendentes_de_metrica(horas_desde_publicacao, limit)
                 if p["plataforma"] == "youtube"]
    if not pendentes:
        return {"processadas": 0, "ok": 0, "falhas": 0, "detalhes": []}

    service_data = _build_data_service()
    service_analytics = _build_analytics_service()

    ok, falhas, detalhes = 0, 0, []
    for pub in pendentes:
        try:
            metricas = {}
            metricas.update(_fetch_statistics(pub["external_id"], service=service_data))
            metricas.update(_fetch_watch_metrics(
                pub["external_id"], pub["publicado_em"], service=service_analytics))
            atualizar_metricas(pub["id"], **{k: v for k, v in metricas.items() if v is not None})
            ok += 1
            detalhes.append({"video_id": pub["external_id"], "status": "ok", **metricas})
        except Exception as e:
            falhas += 1
            detalhes.append({"video_id": pub["external_id"], "status": "erro", "erro": str(e)})

    return {"processadas": len(pendentes), "ok": ok, "falhas": falhas, "detalhes": detalhes}
