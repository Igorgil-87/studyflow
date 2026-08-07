"""
cache/ — cache semântico de respostas de LLM.

Evita repetir chamadas de LLM quando a entrada é idêntica (cache exato) ou
muito parecida (cache semântico por embedding). Cada acerto vira um trace com
status="cache_hit" e custo zero, então a economia aparece direto no /obs.

Camadas:
  1. exato     : hash SHA-256 da entrada — barato, sempre ligado, pega re-runs.
  2. semântico : embedding + similaridade de cosseno — pega entradas parecidas
                 (opcional; exige embeddings).

Gate por env: CACHE_ENABLED=1 liga; por padrão fica desligado.
"""
