"""
tools/perplexity_source.py — fonte de tendências via Perplexity Sonar.

A Sonar já faz busca na web e devolve CITAÇÕES (fontes reais) junto da resposta,
o que resolve dois problemas de uma vez: temas atuais (não genéricos) e com fonte.
Usa o modelo mais barato por padrão ('sonar'); configurável por env.

Tudo opcional e fail-open: sem PERPLEXITY_API_KEY, retorna vazio e o resto do
pipeline segue com as outras fontes.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"


def _http_post(url: str, body: bytes, headers: dict, timeout: int):
    try:
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"[perplexity] requisição falhou: {e}")
        return None


def parse_response(data: dict) -> dict:
    """Extrai tópicos e citações de uma resposta da Sonar. Puro/testável."""
    if not data:
        return {"topics": [], "context": "", "links": []}
    try:
        content = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        content = ""

    raw_cites = data.get("citations") or data.get("search_results") or []
    links: list[dict] = []
    for c in raw_cites:
        if isinstance(c, str):
            links.append({"url": c, "title": "", "source": "perplexity"})
        elif isinstance(c, dict) and c.get("url"):
            links.append({"url": c["url"], "title": c.get("title", ""),
                          "source": "perplexity"})

    topics = []
    for line in content.splitlines():
        t = line.strip().lstrip("0123456789.-•*) \t").strip()
        # remove negrito markdown (**), marcadores de citação [7], e dois-pontos final
        t = t.replace("**", "").replace("*", "")
        t = re.sub(r"\[\d+\]", "", t)
        t = re.sub(r"\s{2,}", " ", t).strip()
        # descarta linhas de introdução/cabeçalho ("... são:", "aqui estão", etc.)
        low = t.lower()
        if t.endswith(":") or low.startswith(("os assuntos", "aqui estao",
                "aqui estão", "seguem", "abaixo", "confira", "os temas",
                "principais")):
            continue
        if len(t) >= 8:
            topics.append(t)
    topics = topics[:8]

    context = ""
    if topics:
        context = ("Perplexity (tendências atuais com fontes):\n"
                   + "\n".join(f"  • {t}" for t in topics))
    return {"topics": topics, "context": context, "links": links}


def fetch_controversies(category_label: str, niche: str = "", model: str | None = None,
                        api_key: str | None = None, fetch=None, timeout: int = 20) -> dict:
    """Busca POLÊMICAS e debates atuais (o que 'estoura bolha'). Mesmo parser."""
    api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        return {"topics": [], "context": "", "links": []}
    model = model or os.getenv("PERPLEXITY_MODEL", "sonar")
    alvo = category_label + (f" / {niche}" if niche else "")
    pergunta = (
        f"Liste de 5 a 8 POLÊMICAS, debates acalorados e opiniões divididas em "
        f"alta agora sobre {alvo}, no Brasil e no mundo. Foque no que gera "
        "discussão, choca ou contraria o senso comum. Uma linha específica por item."
    )
    payload = {"model": model, "messages": [
        {"role": "system", "content": "Você lista polêmicas e debates atuais, "
         "específicos e com lastro, em português brasileiro."},
        {"role": "user", "content": pergunta}]}
    body = json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = (fetch or _http_post)(PERPLEXITY_URL, body, headers, timeout)
    out = parse_response(data)
    if out.get("context"):
        out["context"] = out["context"].replace("tendências atuais", "POLÊMICAS atuais")
    return out


def fetch_trends(category_label: str, niche: str = "", model: str | None = None,
                 api_key: str | None = None, fetch=None, timeout: int = 20) -> dict:
    api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        return {"topics": [], "context": "", "links": []}
    model = model or os.getenv("PERPLEXITY_MODEL", "sonar")

    alvo = category_label + (f" / {niche}" if niche else "")
    pergunta = (
        f"Liste de 5 a 8 assuntos MAIS COMENTADOS e EM ALTA agora sobre {alvo}, "
        "no Brasil e no mundo, dos últimos dias. Seja ESPECÍFICO (nomes, eventos, "
        "fatos concretos) — nada genérico. Uma linha curta por assunto."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Você lista tendências atuais e "
             "específicas, em português brasileiro, com base na web."},
            {"role": "user", "content": pergunta},
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Bearer {api_key}",
               "Content-Type": "application/json"}
    data = (fetch or _http_post)(PERPLEXITY_URL, body, headers, timeout)
    return parse_response(data)
