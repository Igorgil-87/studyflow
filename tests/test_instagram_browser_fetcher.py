"""tests/test_instagram_browser_fetcher.py — testa
analytics/instagram_browser_fetcher.py mockando analytics.store (sem
precisar de Postgres de verdade)."""

from unittest.mock import patch

from analytics.instagram_browser_fetcher import importar_metricas, listar_pendentes
from analytics.store import AnalyticsError

_PUBLICACOES = [
    {
        "id": "id-1",
        "url": "https://www.instagram.com/reel/AAA111/",
        "titulo": "Post 1",
        "publicado_em": "2026-08-01T10:00:00",
        "metricas_atualizadas_em": None,
    },
    {
        "id": "id-2",
        "url": "https://www.instagram.com/reel/BBB222/",
        "titulo": "Post 2",
        "publicado_em": "2026-08-02T10:00:00",
        "metricas_atualizadas_em": "2026-08-03T10:00:00",  # já tem métrica
    },
]


def test_importar_metricas_ok():
    with patch(
        "analytics.instagram_browser_fetcher.list_publicacoes", return_value=_PUBLICACOES
    ), patch("analytics.instagram_browser_fetcher.atualizar_metricas") as mock_update:
        resultado = importar_metricas(
            [{"url": "https://www.instagram.com/reel/AAA111/", "views": 1000, "likes": 50}]
        )

    assert resultado == {
        "processados": 1,
        "ok": 1,
        "falhas": 0,
        "detalhes": [
            {"url": "https://www.instagram.com/reel/AAA111/", "status": "ok",
             "views": 1000, "likes": 50}
        ],
    }
    mock_update.assert_called_once_with("id-1", views=1000, likes=50)


def test_importar_metricas_url_nao_encontrada():
    with patch("analytics.instagram_browser_fetcher.list_publicacoes", return_value=_PUBLICACOES):
        resultado = importar_metricas(
            [{"url": "https://www.instagram.com/reel/NAOEXISTE/", "views": 10}]
        )

    assert resultado["ok"] == 0
    assert resultado["falhas"] == 1
    assert resultado["detalhes"][0]["status"] == "nao_encontrada"


def test_importar_metricas_sem_url():
    with patch("analytics.instagram_browser_fetcher.list_publicacoes", return_value=_PUBLICACOES):
        resultado = importar_metricas([{"views": 10}])
    assert resultado["falhas"] == 1
    assert resultado["detalhes"][0]["erro"] == "item sem 'url'"


def test_importar_metricas_sem_metrica_valida():
    with patch("analytics.instagram_browser_fetcher.list_publicacoes", return_value=_PUBLICACOES):
        resultado = importar_metricas(
            [{"url": "https://www.instagram.com/reel/AAA111/", "campo_invalido": 1}]
        )
    assert resultado["detalhes"][0]["status"] == "sem_metrica_valida"


def test_importar_metricas_lote_vazio():
    assert importar_metricas([]) == {"processados": 0, "ok": 0, "falhas": 0, "detalhes": []}


def test_importar_metricas_erro_no_update_nao_derruba_lote():
    with patch(
        "analytics.instagram_browser_fetcher.list_publicacoes", return_value=_PUBLICACOES
    ), patch(
        "analytics.instagram_browser_fetcher.atualizar_metricas",
        side_effect=AnalyticsError("boom"),
    ):
        resultado = importar_metricas(
            [{"url": "https://www.instagram.com/reel/AAA111/", "views": 10}]
        )

    assert resultado["ok"] == 0
    assert resultado["falhas"] == 1
    assert resultado["detalhes"][0]["status"] == "erro"


def test_listar_pendentes_so_traz_sem_metrica():
    with patch("analytics.instagram_browser_fetcher.list_publicacoes", return_value=_PUBLICACOES):
        pendentes = listar_pendentes()

    assert len(pendentes) == 1
    assert pendentes[0]["url"] == "https://www.instagram.com/reel/AAA111/"
