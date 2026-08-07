"""
infra/bus.py — barramento de eventos para o progresso dos pipelines (SSE).

Substitui o `queue.Queue` por job. Diferenças sobre o original:
  - Vários assinantes podem ouvir o mesmo job (o original só permitia 1).
  - Assinante que conecta TARDE recebe o backlog (replay) e não perde eventos.
  - No modo redis, funciona entre processos/réplicas (web ≠ worker).

Contrato:
  publish(job_id, event, data)         → emite um evento.
  subscribe(job_id) -> generator       → produz (event, data) até "__end__".

O evento terminal é sempre "__end__".
"""

from __future__ import annotations

import json
import queue
import threading
from typing import Iterator

from . import config

_TERMINAL = "__end__"


# ─────────────────────────────────────────────────────────────────────────────
# Backend INLINE (dev): em processo, com replay de backlog.
# ─────────────────────────────────────────────────────────────────────────────
class InlineBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._log: dict[str, list[tuple[str, dict]]] = {}
        self._subs: dict[str, list[queue.Queue]] = {}

    def publish(self, job_id: str, event: str, data: dict) -> None:
        with self._lock:
            self._log.setdefault(job_id, []).append((event, data))
            subs = list(self._subs.get(job_id, []))
        for q in subs:
            q.put((event, data))

    def subscribe(self, job_id: str) -> Iterator[tuple[str, dict]]:
        q: queue.Queue = queue.Queue()
        # Atômico: tira o snapshot do backlog e registra o assinante sob o mesmo
        # lock, para não perder nem duplicar eventos na janela de inscrição.
        with self._lock:
            backlog = list(self._log.get(job_id, []))
            self._subs.setdefault(job_id, []).append(q)

        try:
            for event, data in backlog:
                yield event, data
                if event == _TERMINAL:
                    return
            while True:
                event, data = q.get()
                yield event, data
                if event == _TERMINAL:
                    return
        finally:
            with self._lock:
                if q in self._subs.get(job_id, []):
                    self._subs[job_id].remove(q)


# ─────────────────────────────────────────────────────────────────────────────
# Backend REDIS (prod): Pub/Sub + lista de log para replay, com seq anti-duplo.
# ─────────────────────────────────────────────────────────────────────────────
class RedisBus:
    def __init__(self, url: str) -> None:
        import redis  # import tardio: só exigido no modo redis

        self._r = redis.Redis.from_url(url, decode_responses=True)

    def _keys(self, job_id: str):
        return (
            f"bus:chan:{job_id}",   # canal pub/sub
            f"bus:log:{job_id}",    # lista de eventos (replay)
            f"bus:seq:{job_id}",    # contador monotônico
        )

    def publish(self, job_id: str, event: str, data: dict) -> None:
        chan, logk, seqk = self._keys(job_id)
        seq = self._r.incr(seqk)
        payload = json.dumps({"seq": seq, "event": event, "data": data},
                             ensure_ascii=False)
        pipe = self._r.pipeline()
        pipe.rpush(logk, payload)
        pipe.expire(logk, config.JOB_TTL_SECONDS)
        pipe.expire(seqk, config.JOB_TTL_SECONDS)
        pipe.publish(chan, payload)
        pipe.execute()

    def subscribe(self, job_id: str) -> Iterator[tuple[str, dict]]:
        chan, logk, _ = self._keys(job_id)
        pubsub = self._r.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(chan)
        try:
            # 1) Replay do backlog já gravado.
            seen = 0
            for raw in self._r.lrange(logk, 0, -1):
                msg = json.loads(raw)
                seen = max(seen, msg["seq"])
                yield msg["event"], msg["data"]
                if msg["event"] == _TERMINAL:
                    return
            # 2) Ao vivo, pulando o que já foi entregue no replay (seq <= seen).
            for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                msg = json.loads(message["data"])
                if msg["seq"] <= seen:
                    continue
                yield msg["event"], msg["data"]
                if msg["event"] == _TERMINAL:
                    return
        finally:
            try:
                pubsub.close()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Singleton resolvido por modo.
# ─────────────────────────────────────────────────────────────────────────────
_bus = None


def get_bus():
    global _bus
    if _bus is None:
        _bus = RedisBus(config.REDIS_URL) if config.is_redis() else InlineBus()
    return _bus


def publish(job_id: str, event: str, data: dict) -> None:
    get_bus().publish(job_id, event, data)


def subscribe(job_id: str) -> Iterator[tuple[str, dict]]:
    return get_bus().subscribe(job_id)


def end(job_id: str) -> None:
    """Emite o evento terminal."""
    publish(job_id, _TERMINAL, {})
