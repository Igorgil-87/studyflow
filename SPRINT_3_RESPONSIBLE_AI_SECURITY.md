# Sprint 3 — Responsible AI & Security

Controles implementados sem alterar os pipelines de mídia/Youtuber:

- AI Input Guard determinístico em `/api/rag/query`, `/api/rag/retrieve` e Tutor/Georgina.
- Modos `off`, `monitor` e `enforce` via `AI_GUARD_MODE`.
- Detecção auditável de tentativas comuns de override de instrução, exfiltração de system prompt/secrets e abuso de ferramentas.
- Output Guard com redação de padrões óbvios de API keys/tokens antes da resposta chegar ao browser.
- Audit trail SQLite (`security_events`) com trace, target, risco e motivos, sem gravar o conteúdo completo da pergunta.
- Cookies `HttpOnly`, `SameSite`, `Secure` configurável e headers básicos de browser hardening.
- Dashboard `/security` e APIs `/api/security/summary`, `/api/security/events`.
- O painel de secrets não lê nem exibe valores: apenas sinaliza defaults e presença de arquivos conhecidos.
- A autorização de curso/aula existente continua sendo aplicada antes do Tutor, mantendo isolamento por `user_key` naquele fluxo.

## Limite assumido

Heurísticas de prompt injection não provam ausência de ataques. Por isso o dashboard diferencia controles implementados de postura de produção e mantém evidência/auditoria. O RAG genérico de vídeos continua compatível com os dados legados; isolamento multi-tenant do índice inteiro deve ser ativado quando houver ownership persistido para todos os chunks históricos.
