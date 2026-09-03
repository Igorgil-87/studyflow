# Sprint 5 — Production Engineering, Observability & Reproducibility

## Objetivo
Transformar a operação do StudyFlow em evidência demonstrável para o case: liveness, readiness, dependências, fila/workers, p50/p95, error rate e um preflight de reprodutibilidade.

## Novos endpoints
- `GET /healthz`: liveness, sem dependências.
- `GET /readyz`: readiness, retorna HTTP 503 quando uma dependência obrigatória do modo atual falha.
- `GET /system`: dashboard autenticado.
- `GET /api/system/health`: snapshot operacional autenticado.

## Regras de readiness
- Redis é obrigatório somente quando `RUN_MODE=redis`.
- Postgres + pgvector são obrigatórios quando `RAG_ENABLED=1`.
- Crawl4AI e MoneyPrinter são observados como opcionais; não derrubam readiness do core.
- AI providers aparecem apenas como configured/unconfigured. O health check nunca dispara chamada paga.

## Fila
Em Redis/RQ o dashboard lê queued, started, failed e workers. Em `inline`, reporta o modo sem exigir Redis.

## Reprodutibilidade
Rode:
```bash
python scripts/verify_reproducibility.py
```
O preflight valida a presença do Dockerfile, Compose local/prod, `.env.example`, dependências, processos web/worker/scheduler, init do pgvector e README.

## Demonstração para a banca
1. Abrir `/system`.
2. Mostrar `/healthz` vs `/readyz` e explicar liveness vs readiness.
3. Mostrar Redis/Postgres/pgvector, fila e workers.
4. Mostrar p50/p95 e taxa de erro reais das chamadas observadas.
5. Derrubar uma dependência obrigatória em ambiente controlado e mostrar `503` no `/readyz`.
6. Executar `python scripts/verify_reproducibility.py`.
