# Roteiro de Demo — 90 minutos

## 0–10 min · problema e proposta
Abra `/case`, explique a dor e a tese Knowledge-to-Learning. Mostre a matriz de evidências.

## 10–25 min · arquitetura
Use o diagrama do `/case`. Explique separação de Experience, Orchestration, Knowledge, Responsible AI, Platform e Models. Mostre os trade-offs de RAG vs fine-tuning e multi-provider.

## 25–50 min · demo end-to-end
Use um documento novo: upload → extração/indexação → curso → aula/flashcards/quiz → pergunta à Georgina → resposta com fonte/citação. Evite depender de material previamente cacheado sem explicar.

## 50–62 min · RAG explicável
Abra `/rag`, faça retrieval e mostre Top-K, score, documento, página/chunk e trace. Explique o que acontece antes da geração.

## 62–72 min · avaliação
Abra `/obs`: groundedness, relevância, source fidelity, completeness, hallucination rate, Quality Gate e benchmark. Se a amostra for insuficiente, diga isso explicitamente.

## 72–80 min · Responsible AI
Abra `/security`. Faça uma tentativa controlada de prompt injection e mostre o bloqueio/audit trail. Explique secrets e gaps detectados pelo próprio painel.

## 80–86 min · modelos e produção
Abra `/models` para comparar providers (somente se houver keys/custo aprovado). Abra `/system`, `/healthz` e `/readyz` para readiness, fila, providers e latências.

## 86–90 min · trade-offs e roadmap
Mostre documentação, limitações conhecidas e próximos passos. Termine voltando à matriz: requisito → implementação → evidência.
