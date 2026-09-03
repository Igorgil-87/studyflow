# Arquitetura do Case

```text
Usuário
  │
  ▼
Experience Layer
Georgina / Creator / Youtuber / Case Cockpit
  │
  ▼
AI Orchestration
Course Pipeline ─ Tutor Agent ─ AI Gateway ─ Quality Gates
  │                              │
  │                              ├─ Gemini
  │                              ├─ OpenAI
  │                              └─ Anthropic
  ▼
Knowledge Layer
Extraction → Chunking → Embeddings → pgvector → Top-K → Citations
  │
  ▼
Responsible AI
Input Guard → Ownership → Context Isolation → Output Guard → Audit
  │
  ▼
Platform
Flask → Redis/RQ Workers → PostgreSQL/pgvector → Observability → Docker
```

## Fluxo RAG
Fonte → parser → chunks + metadados → embeddings → pgvector. Na pergunta: embedding da query → busca Top-K → contexto com origem → LLM → resposta com citações → avaliação/telemetria.

## Fluxo de qualidade
Resposta → LLM-as-Judge → groundedness/relevance/source fidelity/completeness → hallucination flag → Quality Gate → histórico observável.

## Fluxo operacional
`/healthz` prova que o processo está vivo. `/readyz` testa dependências obrigatórias do modo atual. `/system` agrega infraestrutura, fila, providers e latência sem chamar APIs pagas de LLM.
