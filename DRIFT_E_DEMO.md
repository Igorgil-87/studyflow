# Drift de IA + roteiro de demonstração

## O que é

`obs/drift.py` compara uma janela **recente** com uma janela **baseline** sobre
a série temporal que já gravamos em `traces` e `evals`, e dispara **alertas**
quando uma métrica piora além do limiar. Não chama LLM — só lê o que existe.

Métricas monitoradas: latência (média e p95), taxa de erro, custo médio por
chamada, judge_score, taxa de alucinação e cache hit rate.

| Endpoint | O quê |
|---|---|
| `GET /api/observability/drift` | computa o drift agora (não persiste) |
| `POST /api/observability/drift/check` | computa **e** salva um snapshot em `drift_runs` |
| Tela `/obs` | painel "Drift de IA" com baseline × recente e alertas coloridos |

Limiares configuráveis no `.env`:

| Variável | Default | Dispara quando |
|---|---|---|
| `DRIFT_RECENT_HOURS` | `24` | tamanho da janela recente |
| `DRIFT_BASELINE_HOURS` | `168` | tamanho da janela baseline (7 dias) |
| `DRIFT_LATENCY_PCT` | `0.30` | p95 sobe >30% |
| `DRIFT_ERROR_ABS` | `0.05` | erro sobe >5 pontos percentuais |
| `DRIFT_COST_PCT` | `0.50` | custo médio sobe >50% |
| `DRIFT_JUDGE_DROP_ABS` | `0.10` | judge_score cai >0.10 |
| `DRIFT_HALLUC_ABS` | `0.10` | alucinação sobe >10 p.p. |
| `DRIFT_MIN_SAMPLES` | `5` | mínimo de amostras por janela para avaliar |

---

## Roteiro para a apresentação (certificação)

A ideia é mostrar o ciclo completo **em tela**, sem depender de dados reais
acumulados por dias.

**1. Suba o app**

```bash
CACHE_ENABLED=1 EVAL_ENABLED=1 python app.py
```

**2. Popule dados de demonstração** (noutro terminal, com o venv ativo)

```bash
python seed_demo.py
```

Isso cria uma janela **baseline saudável** (~5 dias atrás) e uma janela
**recente degradada** (últimas horas): latência maior, mais erro, judge mais
baixo e mais alucinação. São dados fictícios, claramente rotulados.

**3. Abra o dashboard**

`http://localhost:5000/obs` — mostre, de cima para baixo:

- KPIs de custo/chamadas e os cartões de **cache** (acertos e economia em USD);
- custo e volume por modelo (as duas IAs lado a lado);
- latência p50/p95 por operação;
- qualidade (LLM-as-Judge) e feedback 👍/👎;
- o painel **Drift**: clique em **"Rodar verificação de drift"** — a tela
  acende com o selo de alerta e a lista colorida (latência, erro, custo, judge,
  alucinação), com baseline → recente em cada linha.

**4. Mostre o ciclo real** (se tiver chave configurada)

Gere o mesmo quiz duas vezes no módulo Curso: na segunda, o **cache** evita a
chamada e a economia aparece no `/obs`. Cada geração também roda o
**LLM-as-Judge** (porque subiu com `EVAL_ENABLED=1`).

**5. Limpe os dados de demonstração** antes de medir uso real

```bash
python seed_demo.py --reset
```

---

## O que está testado

`_drift_test.py` popula o cenário degradado e valida que os alertas certos
disparam (latência, erro, judge, alucinação), que o snapshot persiste em
`drift_runs`, e que um cenário **estável não gera alerta** (sem falso positivo).

```bash
python _drift_test.py
```

---

## Agendador automático (scheduler.py) — IMPLEMENTADO

O drift agora também roda **sozinho**, em um processo próprio leve:

```bash
python scheduler.py            # loop contínuo (intervalo via env)
python scheduler.py --once     # uma verificação e sai (ideal p/ cron/CronJob K8s)
```

A cada `DRIFT_INTERVAL_SECONDS` ele roda a verificação, **persiste** em
`drift_runs` (aparece no histórico da tela /obs) e, se houver alerta, **notifica
via webhook** (`DRIFT_WEBHOOK_URL` — compatível com Slack/Discord/endpoint
próprio), respeitando um cooldown anti-spam.

| Variável | Default | Efeito |
|---|---|---|
| `DRIFT_INTERVAL_SECONDS` | `3600` | intervalo entre verificações |
| `DRIFT_NOTIFY_COOLDOWN_MIN` | `60` | cooldown entre notificações do mesmo alerta |
| `DRIFT_WEBHOOK_URL` | vazio | webhook de alerta (vazio = só loga) |

No Docker Compose já existe o serviço `scheduler` (1 réplica). Tudo fail-open:
sem webhook configurado, ele apenas registra o alerta no log e na tela.

**Para a demo:** suba `python scheduler.py` num terminal à parte com
`DRIFT_INTERVAL_SECONDS=15`, rode `python seed_demo.py`, e mostre o histórico de
verificações se preenchendo sozinho na seção de drift do `/obs`.

## Limite honesto / próximo passo

A notificação sai por webhook genérico. Conectar num canal real (Slack/Discord)
é só colar a URL no `.env`. Para e-mail, trocaria o `obs/notify.py` por um envio
SMTP — a interface (`send_alert`) já isola isso.
