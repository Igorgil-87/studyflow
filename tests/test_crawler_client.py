"""tests/test_crawler_client.py — testa tools/crawler_client.py (fail-open
quando o serviço Crawl4AI não está disponível — sem precisar do serviço
Docker de verdade rodando pra testar isso)."""

import importlib.util
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_crawler_client():
    """Importa direto do arquivo, contornando tools/__init__.py (mesmo
    motivo dos outros testes — ver test_anti_slop.py)."""
    spec = importlib.util.spec_from_file_location(
        "crawler_client", _PROJECT_ROOT / "tools" / "crawler_client.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_crawler_fail_open_quando_servico_indisponivel(monkeypatch):
    """Se o serviço Crawl4AI não responder, crawl_urls() levanta
    CrawlerError com mensagem clara — não trava, não derruba o
    pipeline chamador."""
    monkeypatch.setenv("CRAWL4AI_URL", "http://localhost:1")  # porta que nunca vai responder
    crawler_client = _load_crawler_client()

    assert crawler_client.is_alive() is False

    try:
        crawler_client.crawl_urls(["https://example.com"])
        assert False, "deveria ter levantado CrawlerError"
    except crawler_client.CrawlerError as e:
        assert "não respondeu" in str(e) or "health" in str(e).lower()


def test_crawl_urls_lista_vazia_nao_chama_servico():
    """Lista de URLs vazia retorna {} direto, sem nem tentar checar o
    serviço (evita uma chamada de rede desnecessária)."""
    crawler_client = _load_crawler_client()
    result = crawler_client.crawl_urls([])
    assert result == {}
