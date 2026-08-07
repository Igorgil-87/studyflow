# Observabilidade + Evals + Feedback (camada `obs/`)

Responde às três perguntas que o app antes não conseguia responder:
**quanto custou/demorou cada IA**, **a saída presta** e **o que o usuário achou**.

Tudo é *fail-open*: uma falha de observabilidade nunca derruba o pipeline.

---

## Componentes

| Arquivo | Papel |
|---|---|
| `obs/db.py` | store SQLite: tabelas `traces`, `feedback`, `evals` (WAL, best-effort) |
| `obs/pricing.py` | tabela de preços por modelo + estimativa de tokens/custo |
| `obs/tracing.py` | `traced_llm(...)` — funil único: resiliência (timeout+breaker) **+** trace |
| `obs/judge.py` | LLM-as-Judge: avalia a qualidade do quiz vs. transcript |
| `obs/report.py` | agregações para o dashboard |
| `templates/obs.html` | dashboard dark em `/obs` |

### O que cada chamada de LLM passa a registrar

`traced_llm` substituiu o `guard` nos pipelines. Cada chamada grava um trace
ligado ao `trace_id` (= `job_id`): operação (`quiz`, `roadmap`, `highlights`,
`trends_synthesize`...), provider, modelo, latência, status, tokens e custo.

> **Honestidade sobre os números:** as tools encapsulam a chamada e nem sempre
> expõem o `usage` real, então tokens são **estimados** (tiktoken, ou heurística
> `len/4`) e o custo usa uma tabela **aproximada** em `obs/pricing.py`. Servem
> para comparação relativa e FinOps, não para fechar fatura. Ajuste os preços
> conforme a tabela vigente.

---

## Endpoints e telas

| Rota | O quê |
|---|---|
| `GET /obs` | dashboard: custo por modelo, latência p50/p95, evals, feedback |
| `GET /api/observability/summary` | o mesmo, em JSON |
| `POST /api/feedback` | registra 👍/👎 de um job |

---

## Como ligar

Nada obrigatório — o tracing já roda por padrão (`OBS_TRACING=1`). Para a
avaliação automática do quiz (custa 1 chamada de LLM por job):

```bash
EVAL_ENABLED=1 python app.py
```

Depois de gerar alguns quizzes/cortes, abra **http://localhost:5000/obs**.

### Botão de feedback no frontend (👍/👎)

O `job_id` que o front já recebe do `/api/generate` é o `trace_id`. Basta um
fetch:

```js
async function enviarFeedback(jobId, vote) {   // vote: 'up' | 'down'
  await fetch('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_id: jobId, target: 'quiz', vote })
  });
}
// <button onclick="enviarFeedback(jobId,'up')">👍</button>
// <button onclick="enviarFeedback(jobId,'down')">👎</button>
```

---

## O que está testado

`_obs_core_test.py` e `_obs_eval_test.py` cobrem, sem chaves nem rede:
preço/estimativa de custo, gravação de traces (sucesso e erro), feedback,
LLM-as-Judge (com stub e em modo fail-open) e as agregações do dashboard.

```bash
python _obs_core_test.py
python _obs_eval_test.py
```

O que **só** dá pra validar na sua máquina (precisa de chave/LLM): o judge real
chamando o modelo e o custo aparecendo no `/obs` após jobs de verdade.

---

## Limites honestos (próximos passos)

- **SQLite** é ótimo para dev e nó único. Em modo redis multi-contêiner, vários
  workers escrevendo no mesmo arquivo exigem volume compartilhado e cuidam mal
  de concorrência alta — o passo seguinte é apontar o store para **Postgres**
  (a interface em `obs/db.py` isola isso).
- Tokens/custo são estimados (ver acima). Para custo exato, o caminho é capturar
  o `usage` real via callback do LangChain (ex.: `get_openai_callback`) dentro
  das tools — fica como evolução.
- **Drift** (comparar qualidade/latência/custo ao longo do tempo) sai de graça
  a partir daqui: já temos a série temporal em `traces`/`evals`; falta só o job
  que compara janelas e dispara alerta.
