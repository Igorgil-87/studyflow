from __future__ import annotations

import os
import time
from dataclasses import dataclass, asdict
from typing import Any

SUPPORTED_PROVIDERS = ("gemini", "openai", "anthropic")

DEFAULT_MODELS = {
    "gemini": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    "openai": os.getenv("LLM_MODEL", "gpt-4o-mini"),
    "anthropic": os.getenv("CLAUDE_MODEL", os.getenv("COURSE_ENGINE_MODEL", "claude-sonnet-4-6")),
}

KEY_ENV = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


class AIGatewayError(RuntimeError):
    """Nenhum provedor configurado/conectado conseguiu responder."""


@dataclass
class GatewayResult:
    text: str
    provider: str
    model: str
    latency_ms: float
    attempts: list[dict]
    trace_id: str | None = None

    def to_dict(self, include_text: bool = True) -> dict:
        data = asdict(self)
        if not include_text:
            data.pop("text", None)
        return data


def _clean_provider(name: str | None) -> str:
    value = (name or "").strip().lower()
    aliases = {"claude": "anthropic", "google": "gemini", "gpt": "openai"}
    return aliases.get(value, value)


def _fallbacks_from_env() -> list[str]:
    raw = os.getenv("AI_FALLBACK_PROVIDERS", "openai,anthropic")
    out: list[str] = []
    for item in raw.split(","):
        p = _clean_provider(item)
        if p in SUPPORTED_PROVIDERS and p not in out:
            out.append(p)
    return out


def gateway_config() -> dict:
    primary = _clean_provider(os.getenv("AI_PRIMARY_PROVIDER", "anthropic"))
    if primary not in SUPPORTED_PROVIDERS:
        primary = "anthropic"
    return {
        "enabled": os.getenv("AI_GATEWAY_ENABLED", "1") != "0",
        "primary_provider": primary,
        "fallback_providers": _fallbacks_from_env(),
        "models": {p: _model_for(p) for p in SUPPORTED_PROVIDERS},
        "timeout_seconds": float(os.getenv("AI_GATEWAY_TIMEOUT", "60")),
    }


def _model_for(provider: str, override: str | None = None) -> str:
    if override:
        return override
    if provider == "gemini":
        return os.getenv("GEMINI_MODEL", DEFAULT_MODELS[provider])
    if provider == "openai":
        return os.getenv("LLM_MODEL", DEFAULT_MODELS[provider])
    return os.getenv("CLAUDE_MODEL", os.getenv("COURSE_ENGINE_MODEL", DEFAULT_MODELS[provider]))


def _is_configured(provider: str) -> bool:
    return bool(os.getenv(KEY_ENV[provider], "").strip())


def configured_providers() -> list[str]:
    return [p for p in SUPPORTED_PROVIDERS if _is_configured(p)]


def provider_status() -> list[dict]:
    cfg = gateway_config()
    return [
        {
            "provider": p,
            "configured": _is_configured(p),
            "model": _model_for(p),
            "primary": p == cfg["primary_provider"],
            "fallback": p in cfg["fallback_providers"],
            "key_env": KEY_ENV[p],
        }
        for p in SUPPORTED_PROVIDERS
    ]


def _normalise_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for msg in messages:
        role = str(msg.get("role") or "user").lower()
        if role in ("assistant", "ai", "model"):
            role = "assistant"
        elif role == "system":
            role = "system"
        else:
            role = "user"
        content = str(msg.get("content") or "")
        if content:
            out.append({"role": role, "content": content})
    return out


def _call_openai(messages: list[dict[str, str]], model: str, temperature: float, max_tokens: int) -> str:
    import openai
    client = openai.OpenAI()
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=messages,
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("OpenAI retornou resposta vazia")
    return text


def _call_anthropic(messages: list[dict[str, str]], model: str, temperature: float, max_tokens: int) -> str:
    import anthropic
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    anthropic_messages = []
    for m in messages:
        if m["role"] == "system":
            continue
        role = "assistant" if m["role"] == "assistant" else "user"
        anthropic_messages.append({"role": role, "content": m["content"]})
    client = anthropic.Anthropic()
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": anthropic_messages,
    }
    if system_parts:
        kwargs["system"] = "\n\n".join(system_parts)
    resp = client.messages.create(**kwargs)
    text = "".join(
        block.text for block in resp.content if getattr(block, "type", "") == "text"
    ).strip()
    if not text:
        raise RuntimeError("Anthropic retornou resposta vazia")
    return text


def _call_gemini(messages: list[dict[str, str]], model: str, temperature: float, max_tokens: int) -> str:
    """Gemini Developer API via REST, sem adicionar outro SDK ao projeto.

    A chave segue somente no request server-side e nunca é devolvida para o
    frontend/log de configuração.
    """
    import requests

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY não configurada")

    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    contents = []
    for m in messages:
        if m["role"] == "system":
            continue
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    if system_parts:
        payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}

    timeout = float(os.getenv("AI_GATEWAY_TIMEOUT", "60"))
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    resp = requests.post(url, params={"key": api_key}, json=payload, timeout=timeout)
    if not resp.ok:
        # Não inclui URL completa porque querystring contém secret.
        detail = resp.text[:500]
        raise RuntimeError(f"Gemini HTTP {resp.status_code}: {detail}")
    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        feedback = data.get("promptFeedback") or {}
        raise RuntimeError(f"Gemini sem candidate. promptFeedback={feedback}")
    parts = (((candidates[0].get("content") or {}).get("parts")) or [])
    text = "".join(str(p.get("text") or "") for p in parts).strip()
    if not text:
        raise RuntimeError("Gemini retornou resposta vazia")
    return text


def _call_provider(provider: str, messages: list[dict[str, str]], model: str,
                   temperature: float, max_tokens: int) -> str:
    if provider == "openai":
        return _call_openai(messages, model, temperature, max_tokens)
    if provider == "anthropic":
        return _call_anthropic(messages, model, temperature, max_tokens)
    if provider == "gemini":
        return _call_gemini(messages, model, temperature, max_tokens)
    raise ValueError(f"Provedor não suportado: {provider}")


def _provider_order(preferred: str | None, fallbacks: list[str] | None) -> list[str]:
    cfg = gateway_config()
    primary = _clean_provider(preferred) if preferred else cfg["primary_provider"]
    if primary not in SUPPORTED_PROVIDERS:
        raise ValueError(f"AI provider inválido: {primary}")
    fb = [_clean_provider(x) for x in (fallbacks if fallbacks is not None else cfg["fallback_providers"])]
    order = [primary] + [p for p in fb if p in SUPPORTED_PROVIDERS and p != primary]
    # Só tenta providers configurados; mantém o primary na lista para gerar erro claro
    # quando nenhum estiver configurado.
    configured = [p for p in order if _is_configured(p)]
    return configured or [primary]


def generate_messages(
    messages: list[dict[str, str]], *, preferred_provider: str | None = None,
    fallback_providers: list[str] | None = None, model: str | None = None,
    temperature: float = 0.2, max_tokens: int = 2048,
    operation: str = "gateway_generate", trace_id: str | None = None,
) -> GatewayResult:
    messages = _normalise_messages(messages)
    if not messages:
        raise ValueError("messages vazio")

    from obs.tracing import traced_llm

    attempts: list[dict] = []
    last_error: Exception | None = None
    input_text = "\n\n".join(m["content"] for m in messages)
    for provider in _provider_order(preferred_provider, fallback_providers):
        chosen_model = _model_for(provider, model if provider == _clean_provider(preferred_provider) else None)
        if not _is_configured(provider):
            attempts.append({"provider": provider, "model": chosen_model, "status": "not_configured"})
            last_error = RuntimeError(f"{KEY_ENV[provider]} não configurada")
            continue
        started = time.monotonic()
        try:
            def _invoke():
                return _call_provider(provider, messages, chosen_model, temperature, max_tokens)
            from obs.context_observability import breakdown_from_messages
            text = traced_llm(
                provider, operation, chosen_model, _invoke,
                trace_id=trace_id, input_text=input_text,
                context_breakdown=breakdown_from_messages(messages, chosen_model),
                timeout=float(os.getenv("AI_GATEWAY_TIMEOUT", "60")),
            )
            latency_ms = round((time.monotonic() - started) * 1000, 2)
            attempts.append({"provider": provider, "model": chosen_model, "status": "ok", "latency_ms": latency_ms})
            return GatewayResult(text=text, provider=provider, model=chosen_model,
                                 latency_ms=latency_ms, attempts=attempts, trace_id=trace_id)
        except Exception as exc:
            latency_ms = round((time.monotonic() - started) * 1000, 2)
            attempts.append({"provider": provider, "model": chosen_model, "status": "error",
                             "latency_ms": latency_ms, "error": str(exc)[:300]})
            last_error = exc

    summary = "; ".join(f"{a['provider']}={a['status']}" for a in attempts)
    raise AIGatewayError(f"Nenhum provedor conseguiu responder ({summary}). Último erro: {last_error}")


def generate_text(
    prompt: str, *, system: str | None = None, preferred_provider: str | None = None,
    fallback_providers: list[str] | None = None, model: str | None = None,
    temperature: float = 0.2, max_tokens: int = 2048,
    operation: str = "gateway_generate", trace_id: str | None = None,
) -> GatewayResult:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return generate_messages(
        messages, preferred_provider=preferred_provider,
        fallback_providers=fallback_providers, model=model,
        temperature=temperature, max_tokens=max_tokens,
        operation=operation, trace_id=trace_id,
    )
