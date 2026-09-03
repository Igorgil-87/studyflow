# Sprint 2 — RAG verificável + citações

## Objetivo
Transformar o RAG em evidência auditável para o case: cada resposta pode mostrar a fonte recuperada, localização (página/slide/timestamp), chunk, similaridade e trace da execução.

## Entregas
- `rag_chunks.metadata_json` (migração aditiva) com `source_name`, `source_type`, `page`, `slide` e `chunk_id`.
- PDFs preservam página; PPTX preserva slide durante a indexação.
- Respostas RAG instruem o LLM a citar `[Fonte N]` e devolvem fontes estruturadas.
- `/rag` ganhou cards de evidência e `Retrieval Debug` expansível.
- `POST /api/rag/retrieve` executa retrieval puro, sem chamada ao LLM.
- Tutor/Georgina devolve `sources` estruturadas e exibe evidências abaixo da resposta.
- Provenance das aulas passa a guardar `source_name`, `page/section` e `score` quando disponíveis.

## Compatibilidade
A migração é aditiva (`ADD COLUMN IF NOT EXISTS`). Vídeos antigos continuam usando timestamp; documentos antigos sem metadata continuam usando chunk como fallback.
