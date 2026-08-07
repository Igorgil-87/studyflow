"""
infra/ — camada de infraestrutura desacoplada do domínio.

Externaliza o estado que antes vivia no processo web (JOBS dict + queue.Queue),
permitindo escala horizontal sem reescrever os pipelines.

Dois modos, escolhidos por env (RUN_MODE):
  - "inline"  → dev: tudo em processo, comportamento idêntico ao original.
  - "redis"   → prod: fila externa (RQ), SSE via Redis Pub/Sub, workers separados.

Princípio: trocar de modo é mudança de ambiente, não de código.
"""
