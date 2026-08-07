"""
infra/config.py — configuração central e detecção de modo de execução.

RUN_MODE define o backend de fila/estado/barramento:
  - "inline" (padrão): sem dependências externas, roda como o app original.
  - "redis": usa Redis para fila (RQ), registro de jobs e Pub/SSE.

Se RUN_MODE não for setado mas REDIS_URL existir, assume "redis".
"""

import os

REDIS_URL = os.getenv("REDIS_URL", "").strip()

# Modo explícito vence; senão, infere pelo REDIS_URL.
RUN_MODE = os.getenv("RUN_MODE", "").strip().lower()
if not RUN_MODE:
    RUN_MODE = "redis" if REDIS_URL else "inline"

# Nome da fila RQ (permite separar filas por tipo de carga no futuro).
QUEUE_NAME = os.getenv("QUEUE_NAME", "studyflow")

# Tempo de vida (segundos) dos logs de evento e metadados de job no Redis.
JOB_TTL_SECONDS = int(os.getenv("JOB_TTL_SECONDS", "3600"))

# Timeout máximo de execução de um job no worker (segundos).
JOB_TIMEOUT_SECONDS = int(os.getenv("JOB_TIMEOUT_SECONDS", "1800"))


def is_redis() -> bool:
    return RUN_MODE == "redis"


def summary() -> str:
    return f"RUN_MODE={RUN_MODE}" + (f" REDIS_URL={REDIS_URL}" if REDIS_URL else "")
