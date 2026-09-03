"""Runtime health/readiness checks for StudyFlow.

The checks are deliberately lightweight and side-effect free.  They never call
paid LLM endpoints; providers are reported as configured/unconfigured only.
"""
from __future__ import annotations

import os
import time
import urllib.request
from typing import Callable


def _result(name: str, ok: bool, latency_ms: float = 0.0, detail: str = "", required: bool = True) -> dict:
    return {
        "name": name,
        "ok": bool(ok),
        "status": "healthy" if ok else "unhealthy",
        "latency_ms": round(float(latency_ms), 2),
        "detail": detail,
        "required": bool(required),
    }


def _timed(name: str, fn: Callable[[], str], *, required: bool = True) -> dict:
    started = time.perf_counter()
    try:
        detail = fn() or "ok"
        return _result(name, True, (time.perf_counter() - started) * 1000, detail, required)
    except Exception as exc:
        return _result(name, False, (time.perf_counter() - started) * 1000, str(exc)[:240], required)


def check_redis(required: bool | None = None) -> dict:
    url = os.getenv("REDIS_URL", "").strip()
    run_mode = os.getenv("RUN_MODE", "").strip().lower()
    req = (run_mode == "redis") if required is None else required
    if not url:
        return _result("redis", not req, detail="not configured", required=req)

    def _ping():
        import redis
        client = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        if not client.ping():
            raise RuntimeError("PING failed")
        return "PING ok"
    return _timed("redis", _ping, required=req)


def check_postgres(required: bool | None = None) -> dict:
    enabled = os.getenv("RAG_ENABLED", "0") != "0"
    req = enabled if required is None else required
    dsn = os.getenv("DATABASE_URL", "postgresql://studyflow:studyflow@localhost:5432/studyflow")
    if not enabled and required is None:
        return _result("postgres_pgvector", True, detail="RAG disabled; optional", required=False)

    def _query():
        import psycopg2
        conn = psycopg2.connect(dsn, connect_timeout=2)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
                cur.execute("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')")
                has_vector = bool(cur.fetchone()[0])
            if not has_vector:
                raise RuntimeError("pgvector extension missing")
        finally:
            conn.close()
        return "Postgres + pgvector ok"
    return _timed("postgres_pgvector", _query, required=req)


def _http_check(name: str, url: str, *, required: bool = False) -> dict:
    if not url:
        return _result(name, True, detail="not configured; optional", required=required)

    def _call():
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "StudyFlow-Health/1.0"})
        with urllib.request.urlopen(req, timeout=2.5) as response:
            code = int(getattr(response, "status", 200))
            if code >= 400:
                raise RuntimeError(f"HTTP {code}")
        return f"HTTP {code}"
    return _timed(name, _call, required=required)


def check_crawl4ai() -> dict:
    base = os.getenv("CRAWL4AI_URL", "").strip().rstrip("/")
    return _http_check("crawl4ai", f"{base}/health" if base else "", required=False)


def check_mpt() -> dict:
    base = os.getenv("MPT_API_URL", "").strip().rstrip("/")
    return _http_check("moneyprinter", f"{base}/openapi.json" if base else "", required=False)


def provider_configuration() -> list[dict]:
    models = {
        "gemini": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        "openai": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "anthropic": os.getenv("CLAUDE_MODEL", os.getenv("COURSE_ENGINE_MODEL", "claude-sonnet-4-6")),
    }
    key_env = {
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    return [
        {"provider": p, "configured": bool(os.getenv(key_env[p], "").strip()), "model": models[p]}
        for p in ("gemini", "openai", "anthropic")
    ]


def queue_metrics() -> dict:
    run_mode = os.getenv("RUN_MODE", "").strip().lower() or ("redis" if os.getenv("REDIS_URL") else "inline")
    if run_mode != "redis":
        return {"mode": "inline", "queue": None, "queued": 0, "started": 0, "failed": 0, "workers": 0, "ok": True}
    try:
        import redis
        from rq import Queue, Worker
        from rq.registry import FailedJobRegistry, StartedJobRegistry
        conn = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), socket_connect_timeout=2, socket_timeout=2)
        queue_name = os.getenv("QUEUE_NAME", "studyflow")
        q = Queue(queue_name, connection=conn)
        return {
            "mode": "redis", "queue": queue_name, "queued": len(q),
            "started": len(StartedJobRegistry(queue_name, connection=conn)),
            "failed": len(FailedJobRegistry(queue_name, connection=conn)),
            "workers": len(Worker.all(connection=conn)), "ok": True,
        }
    except Exception as exc:
        return {"mode": "redis", "queue": os.getenv("QUEUE_NAME", "studyflow"), "queued": None, "started": None, "failed": None, "workers": None, "ok": False, "error": str(exc)[:240]}


def snapshot(include_optional_http: bool = True) -> dict:
    checks = [check_redis(), check_postgres()]
    if include_optional_http:
        checks.extend([check_crawl4ai(), check_mpt()])
    required = [c for c in checks if c["required"]]
    ready = all(c["ok"] for c in required)
    return {
        "status": "ready" if ready else "degraded",
        "ready": ready,
        "run_mode": os.getenv("RUN_MODE", "").strip().lower() or ("redis" if os.getenv("REDIS_URL") else "inline"),
        "checks": checks,
        "queue": queue_metrics(),
        "providers": provider_configuration(),
        "timestamp": time.time(),
    }
