"""
analytics/instagram_browser_fetcher.py — importa métrica do Instagram
coletada via navegador real (skill browser-harness), pra cobrir o caso em
que a API oficial não devolve insight: permissão
instagram_business_manage_insights ainda não liberada pela Meta (o app
hoje só tem instagram_business_basic + instagram_business_content_publish,
ver tools/instagram_client.py), ou conta abaixo de 1000 seguidores.

Não faz nenhuma automação de navegador aqui dentro — isso roda FORA do
Flask, localmente, via browser-harness (ver scripts/browser_harness_instagram_insights.md
pro passo a passo). Esse módulo só recebe o resultado já extraído (JSON)
e grava em analytics/store.py.

Casamento por 'url' (permalink), não por external_id: navegando o site só
se enxerga o shortcode da URL (ex: instagram.com/reel/ABC123/), não o
media_id interno do Graph API. Esse permalink já é gravado tanto na
publicação normal quanto por analytics/instagram_profile.py
(sincronizar_perfil_completo), então serve como chave estável.
"""

from __future__ import annotations

from analytics.store import AnalyticsError, atualizar_metricas, list_publicacoes

# mesmo conjunto aceito por analytics.store.atualizar_metricas, restrito
# ao que dá pra ler na tela de Insights do Instagram (sem watch_time_min
# nem ctr_pct, que são métricas do YouTube)
_ALLOWED = {"views", "alcance", "likes", "comentarios", "compartilhamentos"}


class InstagramBrowserImportError(RuntimeError):
    """Erro ao importar métrica coletada via browser-harness."""


def importar_metricas(dados: list[dict]) -> dict:
    """dados: lista de {"url": <permalink>, + métricas reconhecidas}.

    Fail-open item a item — uma URL que não bate com nenhuma publicação
    registrada, ou sem nenhuma métrica válida, não derruba o resto do
    lote (mesmo padrão de instagram_fetcher.atualizar_metricas_pendentes)."""
    if not dados:
        return {"processados": 0, "ok": 0, "falhas": 0, "detalhes": []}

    publicacoes = {
        p["url"]: p
        for p in list_publicacoes(plataforma="instagram", limit=1000)
        if p.get("url")
    }

    ok, falhas, detalhes = 0, 0, []
    for item in dados:
        url = (item.get("url") or "").strip()
        metricas = {k: v for k, v in item.items() if k in _ALLOWED and v is not None}

        if not url:
            falhas += 1
            detalhes.append({"status": "erro", "erro": "item sem 'url'"})
            continue
        if url not in publicacoes:
            falhas += 1
            detalhes.append({"url": url, "status": "nao_encontrada"})
            continue
        if not metricas:
            falhas += 1
            detalhes.append({"url": url, "status": "sem_metrica_valida"})
            continue

        try:
            atualizar_metricas(publicacoes[url]["id"], **metricas)
            ok += 1
            detalhes.append({"url": url, "status": "ok", **metricas})
        except AnalyticsError:
            falhas += 1
            detalhes.append({"url": url, "status": "erro", "erro": "falha ao atualizar métricas"})

    return {"processados": len(dados), "ok": ok, "falhas": falhas, "detalhes": detalhes}


def listar_pendentes(limit: int = 100) -> list[dict]:
    """Lista posts do Instagram sem métrica ainda — pra saber quais URLs
    o browser-harness precisa visitar. Usado pelo runbook manual."""
    return [
        {"url": p["url"], "titulo": p.get("titulo", ""), "publicado_em": p.get("publicado_em")}
        for p in list_publicacoes(plataforma="instagram", limit=limit)
        if p.get("url") and p.get("metricas_atualizadas_em") is None
    ]
