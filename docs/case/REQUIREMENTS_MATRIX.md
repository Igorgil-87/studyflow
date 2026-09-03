# Matriz de Requisitos e Evidências

| Requisito | Implementação | Evidência principal |
|---|---|---|
| Caso real de negócio | Knowledge-to-Learning multimodal | `/case`, `/curso` |
| Modelos GenAI | AI Gateway Gemini/OpenAI/Anthropic | `/models` |
| Prompts/controlabilidade | Prompts estruturados, versão do judge, guards | `obs/judge.py`, `/security` |
| Dados da empresa | upload, extração, chunks, metadados | `/rag` |
| RAG/estratégia de modelo | pgvector + Top-K + citações | `/api/rag/retrieve` |
| Agentes/orquestração | pipeline de curso, tutor, fila | `pipelines.py`, `curso/tutor_agent.py` |
| Avaliação | LLM-as-Judge + Quality Gates | `/obs` |
| Ética/privacidade | guards, ownership, redaction, audit | `/security` |
| Arquitetura/trade-offs | arquitetura em camadas + decisões documentadas | `docs/case/ARCHITECTURE.md` |
| Reprodutibilidade | Docker + env example + verifier | `scripts/verify_reproducibility.py` |
| Escala/eficiência | workers, cache, health, FinOps | `/system` |
| Documentação/roadmap | pacote do case | `docs/case/` |

A rota `/api/case/summary` calcula a cobertura com base em artefatos concretos do repositório. Cobertura documental não substitui teste funcional: na apresentação, cada requisito deve ser demonstrado com sua evidência correspondente.
