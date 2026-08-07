"""
tools/crawler_client.py — varre páginas da web e devolve o conteúdo já
limpo em Markdown, chamando o servidor Docker OFICIAL do Crawl4AI via
HTTP simples. Cliente compartilhado entre:
  - módulo Curso (indexar uma URL no RAG, junto com PDF/PPTX/DOCX)
  - módulo Trends (contexto extra de páginas de referência na análise)

IMPORTANTE — por que HTTP e não `import crawl4ai`: o pacote Python do
Crawl4AI arrasta a dependência unclecode-litellm, que exige openai>=2.8.0.
Esse projeto trava em openai==1.51.0 (e langchain-openai==0.1.23 exige
openai<2.0.0) — instalar o pacote crawl4ai direto quebra a instalação
inteira (visto na prática: ResolutionImpossible do pip). A saída é rodar
o Crawl4AI como serviço Docker separado (mesmo padrão do Fooocus-API) e
falar com ele só por HTTP — nenhum código deles entra no nosso ambiente
Python, então não tem conflito de versão possível.

Fail-open sempre: se o serviço não estiver no ar, retorna vazio/erro
tratado — nunca derruba quem chamou.
"""

from __future__ import annotations

import os

import requests

CRAWL4AI_URL = os.getenv("CRAWL4AI_URL", "http://crawl4ai:11235").rstrip("/")
_TIMEOUT = 60  # varredura de página pode demorar mais que uma chamada de API comum


class CrawlerError(RuntimeError):
    """Erro ao varrer uma URL."""


def is_alive() -> bool:
    """Confere se o serviço Docker do Crawl4AI está no ar."""
    try:
        r = requests.get(f"{CRAWL4AI_URL}/health", timeout=5)
        return r.status_code == 200
    except requests.RequestException:
        return False


def _extract_markdown(result: dict) -> str:
    """O campo 'markdown' pode vir como string simples ou como objeto
    {'raw_markdown': ..., 'fit_markdown': ...} dependendo da config —
    trata os dois formatos."""
    md = result.get("markdown")
    if isinstance(md, str):
        return md.strip()
    if isinstance(md, dict):
        return (md.get("fit_markdown") or md.get("raw_markdown") or "").strip()
    return ""


def crawl_urls(urls: list[str]) -> dict[str, str]:
    """Varre uma lista de URLs via servidor Docker do Crawl4AI e devolve
    {url: markdown}. URLs que falharem individualmente vêm com string
    vazia. Levanta CrawlerError só se o serviço inteiro estiver fora do
    ar ou a chamada falhar de forma irrecuperável."""
    if not urls:
        return {}
    if not is_alive():
        raise CrawlerError(
            f"Serviço do Crawl4AI não respondeu em {CRAWL4AI_URL}/health — "
            "confira se o container está rodando (docker compose ps)."
        )

    try:
        resp = requests.post(
            f"{CRAWL4AI_URL}/crawl",
            json={"urls": urls, "crawler_config": {"type": "CrawlerRunConfig", "params": {"cache_mode": "bypass"}}},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise CrawlerError(f"Falha ao chamar o Crawl4AI: {exc}") from exc

    body = resp.json()
    results = body.get("results") or []
    out: dict[str, str] = {u: "" for u in urls}
    for r in results:
        url = r.get("url")
        if url and r.get("success"):
            out[url] = _extract_markdown(r)
    return out


def crawl_url(url: str) -> str:
    """Varre UMA URL e devolve o markdown (string vazia se falhar)."""
    return crawl_urls([url]).get(url, "")
