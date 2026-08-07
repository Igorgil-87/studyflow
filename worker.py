"""
worker.py — processo worker (modo redis).

Consome jobs da fila RQ e executa os pipelines, separado do processo web.
Escala independentemente (N workers) e o RQ já faz warm shutdown ao receber
SIGTERM (termina o job atual antes de sair) — bom para rolling deploys no K8s.

Uso:
    RUN_MODE=redis REDIS_URL=redis://localhost:6379/0 python worker.py
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from infra import config  # noqa: E402


def main() -> None:
    if not config.is_redis():
        print("worker.py só faz sentido em RUN_MODE=redis. "
              f"Modo atual: {config.RUN_MODE}.", file=sys.stderr)
        sys.exit(1)

    import redis
    from rq import Queue, Worker

    conn = redis.Redis.from_url(config.REDIS_URL)
    queues = [Queue(config.QUEUE_NAME, connection=conn)]

    print(f"[worker] conectado · fila='{config.QUEUE_NAME}' · {config.summary()}")
    # import dos pipelines para garantir que o worker resolve os caminhos.
    import pipelines  # noqa: F401

    Worker(queues, connection=conn).work(with_scheduler=False)


if __name__ == "__main__":
    main()
