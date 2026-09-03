# Sprint 1B — Quality Gates + Benchmark Controlado

## Objetivo
Transformar as avaliações do LLM-as-Judge em critérios objetivos e auditáveis de aceite para o case de Engenharia de IA.

## Quality Gates padrão
- Groundedness >= 0.85
- Relevance >= 0.85
- Source Fidelity >= 0.90
- Completeness >= 0.80
- Judge Score >= 0.85
- Hallucination Rate <= 0.05
- Amostra mínima: 3 avaliações

Todos os limites são configuráveis por variáveis `QUALITY_*`.

## Endpoints
- `GET /api/observability/quality-gate`
- `GET /api/observability/benchmarks`
- `POST /api/observability/benchmark`

O benchmark recebe até 20 casos com `question`, `context` e `answer`. Ele não gera respostas: mede respostas reais já produzidas. A escolha/comparação automática de providers fica isolada para a Sprint de AI Gateway/Multi-model.

Exemplo de payload:

```json
{
  "suite": "rag-v1",
  "cases": [
    {
      "id": "case-01",
      "label": "Resposta fiel ao documento",
      "target": "rag_answer",
      "question": "Qual é a política descrita?",
      "context": "A política determina revisão anual.",
      "answer": "A política determina revisão anual."
    }
  ]
}
```

## Evidência para a banca
O dashboard `/obs` passa a mostrar:
- estado PASS / FAIL / dados insuficientes;
- métrica atual versus threshold;
- histórico de benchmarks;
- taxa de aprovação;
- rastreabilidade por `trace_id`, modelo juiz e versão do prompt.

Nenhum gate bloqueia o produto nesta sprint. Primeiro medimos e validamos; políticas de bloqueio/rollback pertencem às sprints de Responsible AI/produção.
