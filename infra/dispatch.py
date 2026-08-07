"""
infra/dispatch.py — despacho da execução do pipeline.

Inline → roda numa thread (igual ao original).
Redis  → enfileira no RQ; um processo worker.py separado executa.

A função é referenciada por caminho ("pipelines.run_curso_pipeline") para que
o RQ consiga importá-la no worker.
"""

from __future__ import annotations

import importlib
import threading
from typing import Any

from . import config


def _resolve(path: str):
    module_name, func_name = path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, func_name)


def dispatch(func_path: str, *args: Any) -> None:
    if config.is_redis():
        import redis
        from rq import Queue

        conn = redis.Redis.from_url(config.REDIS_URL)
        q = Queue(config.QUEUE_NAME, connection=conn)
        q.enqueue(func_path, *args, job_timeout=config.JOB_TIMEOUT_SECONDS)
    else:
        func = _resolve(func_path)
        threading.Thread(target=func, args=args, daemon=True).start()
