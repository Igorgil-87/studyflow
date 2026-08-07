"""
obs/ — camada de observabilidade e avaliação de IA (LLMOps).

Quatro subsistemas, todos fail-open (nunca derrubam o pipeline):
  - tracing : registra cada chamada de LLM (operação, modelo, latência, status,
              tokens estimados e custo) ligada ao trace_id (= job_id).
  - pricing : tabela de preços por modelo + estimativa de custo.
  - judge   : LLM-as-Judge — uma IA avalia a saída de outra.
  - feedback: 👍/👎 humano, gravado junto ao trace.

Armazenamento: SQLite (output/observability.db por padrão). Simples, local e
consultável. Em modo redis multi-contêiner, aponte OBS_DB para um volume
compartilhado ou troque por Postgres (ver METRICS_OBS.md).
"""
