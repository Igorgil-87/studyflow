"""
infra/jobs.py — registro de jobs (metadados + resultado final).

Substitui o dict global JOBS. Guarda o estado que sobrevive ao streaming:
status, erro e os resultados (quiz, roadmap, clips, trends...) para endpoints
como /api/quiz/<job_id> lerem depois.

Inline → dict em memória.   Redis → hash `job:<job_id>` (campos JSON), com TTL.
"""

from __future__ import annotations

import json
import threading
from typing import Any

from . import config


class InlineJobs:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, dict] = {}

    def create(self, job_id: str, kind: str) -> None:
        with self._lock:
            self._data[job_id] = {"kind": kind, "done": False, "error": None}

    def exists(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._data

    def set(self, job_id: str, field: str, value: Any) -> None:
        with self._lock:
            if job_id in self._data:
                self._data[job_id][field] = value

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            d = self._data.get(job_id)
            return dict(d) if d else None


class RedisJobs:
    def __init__(self, url: str) -> None:
        import redis

        self._r = redis.Redis.from_url(url, decode_responses=True)

    def _key(self, job_id: str) -> str:
        return f"job:{job_id}"

    def create(self, job_id: str, kind: str) -> None:
        key = self._key(job_id)
        pipe = self._r.pipeline()
        pipe.hset(key, mapping={
            "kind": kind,
            "done": json.dumps(False),
            "error": json.dumps(None),
        })
        pipe.expire(key, config.JOB_TTL_SECONDS)
        pipe.execute()

    def exists(self, job_id: str) -> bool:
        return bool(self._r.exists(self._key(job_id)))

    def set(self, job_id: str, field: str, value: Any) -> None:
        key = self._key(job_id)
        if not self._r.exists(key):
            return
        self._r.hset(key, field, json.dumps(value, ensure_ascii=False))
        self._r.expire(key, config.JOB_TTL_SECONDS)

    def get(self, job_id: str) -> dict | None:
        raw = self._r.hgetall(self._key(job_id))
        if not raw:
            return None
        out: dict[str, Any] = {}
        for k, v in raw.items():
            try:
                out[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                out[k] = v
        return out


_jobs = None


def _backend():
    global _jobs
    if _jobs is None:
        _jobs = RedisJobs(config.REDIS_URL) if config.is_redis() else InlineJobs()
    return _jobs


def create(job_id: str, kind: str) -> None:
    _backend().create(job_id, kind)


def exists(job_id: str) -> bool:
    return _backend().exists(job_id)


def set(job_id: str, field: str, value: Any) -> None:
    _backend().set(job_id, field, value)


def get(job_id: str) -> dict | None:
    return _backend().get(job_id)
