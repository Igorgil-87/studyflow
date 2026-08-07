"""
cache/llm_cache.py — ponto de entrada do cache semântico.

`smart_call(...)` substitui `obs.tracing.traced_llm(...)` nos pipelines para as
operações cacheáveis. Comportamento:

  CACHE_ENABLED=0 (padrão) → delega direto ao traced_llm (cache transparente off).
  CACHE_ENABLED=1:
    1. hash exato da chave → acerto? devolve do cache (custo 0, trace cache_hit).
    2. senão, embedding + cosseno → acerto >= threshold? idem.
    3. miss → chama o LLM de verdade (via traced_llm) e guarda o resultado.

result_kind define como o valor é guardado/devolvido:
  - "file": fn retorna um caminho; cacheia o CONTEÚDO e, no acerto, reescreve um
            arquivo novo em file_dir e devolve o caminho (downstream inalterado).
  - "text": fn retorna string (JSON-como-texto); cacheia/devolve como está.
  - "json": fn retorna dict/list; cacheia serializado e devolve desserializado.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path

from infra.resilience import _RAISE
from obs import db as obs_db
from obs.tracing import traced_llm
from . import embeddings, store

CACHE_ENABLED = os.getenv("CACHE_ENABLED", "0") == "1"
SIM_THRESHOLD = float(os.getenv("CACHE_SIM_THRESHOLD", "0.95"))

if CACHE_ENABLED:
    store.init()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _record_hit(trace_id, operation, provider, model, similarity):
    obs_db.insert_trace({
        "trace_id": trace_id, "ts": time.time(),
        "operation": operation, "provider": provider, "model": model,
        "latency_ms": 0.0, "status": "cache_hit",
        "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
        "error": None if similarity is None else f"sim={similarity}",
    })


def _payload_from_result(result, result_kind: str):
    """(payload_str, file_ext) ou (None, None) se não deve cachear."""
    if result_kind == "file":
        if not isinstance(result, str) or result.startswith("ERRO"):
            return None, None
        if not (os.path.exists(result) and os.path.isfile(result)):
            return None, None
        with open(result, encoding="utf-8") as f:
            return f.read(), os.path.splitext(result)[1] or ".json"
    if result_kind == "text":
        if not isinstance(result, str) or result.startswith("ERRO"):
            return None, None
        return result, None
    if result_kind == "json":
        if not result:                 # não cacheia fallback vazio ({}, [], None)
            return None, None
        return json.dumps(result, ensure_ascii=False), None
    return None, None


def _materialize_hit(entry: dict, result_kind: str, file_dir: str | None):
    payload = entry["result_payload"]
    if result_kind == "file":
        ext = entry.get("file_ext") or ".json"
        out_dir = file_dir or "output"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        path = os.path.join(out_dir, f"cachehit_{uuid.uuid4().hex[:8]}{ext}")
        with open(path, "w", encoding="utf-8") as f:
            f.write(payload)
        return path
    if result_kind == "json":
        return json.loads(payload)
    return payload  # text


def smart_call(
    provider: str,
    operation: str,
    model: str,
    fn,
    *args,
    cache_key: str,
    result_kind: str,
    trace_id: str | None = None,
    input_text: str = "",
    file_dir: str | None = None,
    timeout: float | None = 180.0,
    fallback=_RAISE,
    **kwargs,
):
    # Cache desligado → caminho normal (apenas resiliência + trace).
    if not CACHE_ENABLED:
        return traced_llm(provider, operation, model, fn, *args,
                         trace_id=trace_id, input_text=input_text,
                         timeout=timeout, fallback=fallback, **kwargs)

    namespace = operation
    h = _hash(cache_key)

    # 1) exato
    entry = store.get_exact(namespace, h)
    query_emb = None
    # 2) semântico
    if entry is None:
        query_emb = embeddings.embed(cache_key)
        if query_emb is not None:
            entry = store.search_semantic(namespace, query_emb, SIM_THRESHOLD)

    if entry is not None:
        store.incr_hits(entry["id"])
        _record_hit(trace_id, operation, provider, model,
                    entry.get("similarity"))
        return _materialize_hit(entry, result_kind, file_dir)

    # 3) miss → chamada real (rastreada + resiliente)
    result = traced_llm(provider, operation, model, fn, *args,
                       trace_id=trace_id, input_text=input_text,
                       timeout=timeout, fallback=fallback, **kwargs)
    try:
        payload, ext = _payload_from_result(result, result_kind)
        if payload is not None:
            store.put(namespace, h, query_emb, result_kind, payload, ext)
    except Exception as e:
        print(f"[cache.llm_cache] store falhou (seguindo): {e}")
    return result
