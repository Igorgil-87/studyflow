"""
obs/tracing.py — instrumentação de chamadas de LLM.

`traced_llm(...)` é o funil único: aplica resiliência (timeout + circuit breaker
via infra.resilience.guard) E registra um trace (latência, status, tokens
estimados, custo) ligado ao trace_id (= job_id).

Substitui as chamadas a `guard(...)` nos pipelines, com a mesma semântica de
fallback (fail-open opcional).
"""

from __future__ import annotations

import json
import os
import time

from infra.resilience import guard, CircuitOpenError, _RAISE
from . import db, pricing

_TRACE_ENABLED = os.getenv("OBS_TRACING", "1") != "0"


def _materialize(result) -> str:
    """Texto de saída para estimar tokens: lê arquivo se for caminho, senão serializa."""
    try:
        if isinstance(result, str):
            if os.path.exists(result) and os.path.isfile(result):
                with open(result, encoding="utf-8") as f:
                    return f.read()
            return result
        return json.dumps(result, ensure_ascii=False)
    except Exception:
        return ""


def traced_llm(
    provider: str,
    operation: str,
    model: str,
    fn,
    *args,
    trace_id: str | None = None,
    input_text: str = "",
    timeout: float | None = 60.0,
    fallback=_RAISE,
    **kwargs,
):
    """
    Executa fn com resiliência + tracing.

    provider  : "openai" | "anthropic" (chave do circuit breaker)
    operation : "quiz" | "roadmap" | "highlights" | "trends_synthesize" ...
    model     : nome do modelo (para custo)
    trace_id  : job_id, liga o trace ao job
    input_text: texto de entrada para estimar tokens de input
    fallback  : _RAISE (propaga) ou um valor (fail-open)
    """
    start = time.monotonic()
    status = "ok"
    error_msg = None
    result = None
    try:
        result = guard(provider, fn, *args, timeout=timeout, fallback=_RAISE, **kwargs)
        return result
    except CircuitOpenError as e:
        status, error_msg = "circuit_open", str(e)
        if fallback is _RAISE:
            raise
        result = fallback
        return result
    except Exception as e:
        status = "error"
        error_msg = str(e)[:500]
        if fallback is _RAISE:
            raise
        result = fallback
        return result
    finally:
        if _TRACE_ENABLED:
            try:
                latency_ms = round((time.monotonic() - start) * 1000, 2)
                out_text = _materialize(result) if status == "ok" else ""
                in_tok = pricing.estimate_tokens(input_text, model)
                out_tok = pricing.estimate_tokens(out_text, model)
                db.insert_trace({
                    "trace_id": trace_id,
                    "ts": time.time(),
                    "operation": operation,
                    "provider": provider,
                    "model": model,
                    "latency_ms": latency_ms,
                    "status": status,
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                    "cost_usd": pricing.estimate_cost(model, in_tok, out_tok),
                    "error": error_msg,
                })
            except Exception as e:  # observabilidade nunca derruba o pipeline
                print(f"[obs.tracing] registro falhou: {e}")
