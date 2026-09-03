# Sprint 4 — Multi-Model / Gemini + AI Gateway

## Objetivo
Desacoplar StudyFlow de um único fornecedor de LLM e tornar explícitos os
trade-offs entre Gemini, OpenAI e Anthropic.

## O que entrou
- `ai_gateway/`: interface única para Gemini/OpenAI/Anthropic.
- Gemini Developer API via REST server-side (sem SDK novo e sem expor a chave).
- fallback configurável por ambiente e circuit breaker/tracing por tentativa.
- RAG final response integrado ao Gateway.
- Tutor/Georgina integrado ao Gateway com rollback via `AI_GATEWAY_ENABLED=0`.
- `/models`: painel de providers, rota padrão e laboratório de comparação.
- `POST /api/models/test`: smoke test explícito de um provider.
- `POST /api/models/compare`: mesmo prompt, providers isolados, sem fallback.
- histórico persistido em `model_comparisons`.
- AI Eval opcional durante comparação quando `EVAL_ENABLED=1` e há contexto.

## Segurança
- nenhuma API devolve o valor das chaves;
- Gemini API key é usada somente server-side;
- benchmark é manual para não criar gasto automático;
- `AI Guard` valida o prompt do benchmark;
- erros do Gemini não registram a URL com querystring da chave.

## Configuração sugerida para testar Gemini
```env
AI_GATEWAY_ENABLED=1
AI_PRIMARY_PROVIDER=gemini
AI_FALLBACK_PROVIDERS=openai,anthropic
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
RAG_LLM_PROVIDER=gemini
TUTOR_LLM_PROVIDER=gemini
```

A chave deve ser regenerada caso tenha sido exposta em tela/chat antes de uso
em produção.

## Evidência para o case
Na banca, abrir `/models`, mostrar os três providers e executar o mesmo prompt
em 2–3 modelos. Com `EVAL_ENABLED=1` e contexto de referência, comparar
latência + groundedness + relevance + judge score. Isso demonstra seleção de
modelo baseada em evidência, não preferência de fornecedor.
