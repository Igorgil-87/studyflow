# Decisões e Trade-offs

## RAG em vez de fine-tuning para conhecimento
O conhecimento do cliente é dinâmico, privado e muda por curso/material. RAG reduz custo de atualização e mantém rastreabilidade das fontes. Fine-tuning pode ser útil futuramente para estilo ou tarefas altamente repetitivas, mas não é o mecanismo principal de conhecimento factual.

## Multi-provider em vez de lock-in
O AI Gateway abstrai Gemini, OpenAI e Anthropic. O benefício é resiliência e benchmark; o custo é manter diferenças de API/modelo e uma superfície maior de testes. Benchmarks desabilitam fallback para comparação justa.

## LLM-as-Judge
Permite avaliar groundedness e qualidade semanticamente em escala, mas não é verdade absoluta. Por isso os resultados são tratados como evidência quantitativa complementar, com thresholds explícitos e `insufficient_data` quando não há amostra mínima.

## Guardrails pragmáticos
Prompt-injection detection e output redaction reduzem risco, mas não são uma sandbox formal. O design usa defesa em profundidade: autenticação, ownership, minimização de contexto, guards, auditoria e separação de secrets.

## Redis/RQ opcional
Local pode usar `RUN_MODE=inline` para simplicidade. Produção pode usar `RUN_MODE=redis` para separar web e workers e permitir escala horizontal. Isso preserva experiência de desenvolvimento sem esconder a arquitetura de produção.

## Health sem chamadas pagas
Providers são mostrados como configurados/não configurados no health. Conectividade real é testada manualmente em `/models`, evitando custo e efeitos colaterais em probes automáticos.
