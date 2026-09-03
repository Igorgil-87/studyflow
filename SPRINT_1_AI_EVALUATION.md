# Sprint 1A — AI Evaluation Engine

Esta sprint transforma a observabilidade existente em uma camada de avaliação comparável para respostas RAG e Tutor, preservando os fluxos atuais.

## Entregue
- LLM-as-Judge genérico para respostas grounded.
- Métricas: groundedness, relevance, coherence, source fidelity, completeness, hallucination e judge score.
- Persistência SQLite com migração aditiva do banco existente.
- `trace_id` único por pergunta RAG/Tutor.
- Avaliação automática opt-in com `EVAL_ENABLED=1`.
- Endpoint explícito `POST /api/observability/evaluate` para benchmark/demonstração.
- Dashboard `/obs` enriquecido com as novas métricas.
- Versão de prompt (`EVAL_PROMPT_VERSION`) persistida para auditoria.

## Segurança operacional
`EVAL_ENABLED=0` continua sendo o padrão. Portanto, atualizar para esta sprint não cria custo adicional de LLM até que a avaliação automática seja ativada conscientemente.

## Próxima etapa (Sprint 1B)
Benchmark dataset + comparação por modelo/prompt + quality gates, antes de seguir para a Sprint 2 (RAG & Citations).
