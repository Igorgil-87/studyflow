"""
tools/llm_fallback.py — chamada de LLM com fallback real entre
provedores. Se a Anthropic falhar (erro de API, rate limit, timeout,
serviço fora do ar — não erro de conteúdo/parsing, isso cada chamador
trata do seu jeito), cai pra OpenAI automaticamente, sem quebrar o
pipeline inteiro por causa de UM provedor estar indisponível.

Uso: qualquer código que hoje faz `anthropic.Anthropic().messages.create()`
direto pode trocar por `call_with_fallback(system=..., user=...)` e ganhar
o fallback de graça, sem mudar a lógica de parsing da resposta (que
continua sendo uma string de texto, igual antes).
"""

from __future__ import annotations

import os

DEFAULT_ANTHROPIC_MODEL = os.getenv("CLAUDE_COPY_MODEL", "claude-haiku-4-5-20251001")
DEFAULT_OPENAI_MODEL = os.getenv("LLM_FALLBACK_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini"))


def build_llm_with_fallback(
    temperature: float = 0.3,
    primary_provider: str = "openai",
    primary_model: str | None = None,
    fallback_provider: str = "anthropic",
    fallback_model: str | None = None,
):
    """Versão do fallback pra código que usa chain do LangChain
    (`prompt | llm | parser`), em vez do SDK cru da Anthropic/OpenAI.
    Usa o mecanismo nativo `.with_fallbacks()` do LangChain — o objeto
    retornado funciona como um LLM normal dentro de uma chain, mas por
    baixo dos panos tenta o principal e cai pro alternativo sozinho se
    o principal falhar (erro de API, rate limit, timeout etc.)."""
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic

    primary_model = primary_model or (DEFAULT_OPENAI_MODEL if primary_provider == "openai" else DEFAULT_ANTHROPIC_MODEL)
    fallback_model = fallback_model or (DEFAULT_ANTHROPIC_MODEL if fallback_provider == "anthropic" else DEFAULT_OPENAI_MODEL)

    def _build(provider: str, model: str):
        if provider == "openai":
            return ChatOpenAI(model=model, temperature=temperature)
        return ChatAnthropic(model=model, temperature=temperature)  # type: ignore[call-arg]

    primary = _build(primary_provider, primary_model)
    fallback = _build(fallback_provider, fallback_model)
    return primary.with_fallbacks([fallback])


class LLMFallbackError(RuntimeError):
    """As duas tentativas (Anthropic e OpenAI) falharam."""


def _call_anthropic(system: str, user: str, max_tokens: int, model: str) -> str:
    import anthropic
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
    )
    texto = "".join(
        block.text for block in resp.content if getattr(block, "type", "") == "text"
    ).strip()
    if not texto:
        raise RuntimeError(f"Resposta da Anthropic veio sem bloco de texto (content={resp.content!r})")
    return texto


def _call_openai(system: str, user: str, max_tokens: int, model: str) -> str:
    import openai
    client = openai.OpenAI()
    resp = client.chat.completions.create(
        model=model, max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    texto = (resp.choices[0].message.content or "").strip()
    if not texto:
        raise RuntimeError("Resposta da OpenAI veio vazia")
    return texto


def call_with_fallback(
    system: str, user: str, *, max_tokens: int = 2048,
    anthropic_model: str | None = None, openai_model: str | None = None,
) -> str:
    """Tenta Anthropic primeiro, cai pra OpenAI se a Anthropic falhar de
    verdade (erro de API/rede/limite — não erro de conteúdo, isso quem
    chama trata sozinho). Levanta LLMFallbackError só se OS DOIS
    provedores falharem — nesse caso, sim, não tem mais o que tentar."""
    anthropic_model = anthropic_model or DEFAULT_ANTHROPIC_MODEL
    openai_model = openai_model or DEFAULT_OPENAI_MODEL

    erro_anthropic = None
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            return _call_anthropic(system, user, max_tokens, anthropic_model)
        except Exception as e:
            erro_anthropic = e
            print(f"[llm_fallback] Anthropic falhou ({e}) — tentando OpenAI...")
    else:
        erro_anthropic = RuntimeError("ANTHROPIC_API_KEY não configurada")

    erro_openai = None
    if os.getenv("OPENAI_API_KEY"):
        try:
            return _call_openai(system, user, max_tokens, openai_model)
        except Exception as e:
            erro_openai = e
            print(f"[llm_fallback] OpenAI também falhou ({e}).")
    else:
        erro_openai = RuntimeError("OPENAI_API_KEY não configurada")

    raise LLMFallbackError(
        f"Os dois provedores falharam. Anthropic: {erro_anthropic}. OpenAI: {erro_openai}."
    )
