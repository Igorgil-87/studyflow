# Fila externa, workers e resiliência — guia da Fase 1

Este documento explica o refactor de escala aplicado ao StudyFlow e como rodar
nos dois modos. É o `01_BACKEND` saindo do papel.

---

## O que mudou e por quê

O original guardava cada job num dict global (`JOBS`) e usava uma
`queue.Queue` **dentro do processo web**. Isso quebra assim que sobe a 2ª
réplica: o estado não é compartilhado e o SSE só funciona se o navegador cair
na mesma réplica que rodou o job. Também havia um bug sutil — só **um**
assinante por job conseguia ler a fila.

A Fase 1 externaliza esse estado atrás de uma camada fina (`infra/`), com dois
modos selecionados por env (`RUN_MODE`):

| | `inline` (dev) | `redis` (prod) |
|---|---|---|
| Fila / execução | thread no processo web | RQ + worker separado |
| Progresso (SSE) | barramento em memória | Redis Pub/Sub + replay |
| Registro de jobs | dict em memória | hash no Redis (com TTL) |
| Escala | 1 processo | web e worker escalam separados |

**O mesmo código roda nos dois.** Trocar é mudança de ambiente, não de domínio
— exatamente o princípio "Redis em produção, memória local em dev".

### Arquivos novos (`infra/`)

| Arquivo | Papel |
|---|---|
| `config.py` | lê `RUN_MODE`/`REDIS_URL` e decide o backend |
| `bus.py` | barramento de eventos do SSE (inline e Redis), com **replay** |
| `jobs.py` | registro de jobs (dict ou hash Redis) |
| `dispatch.py` | despacha o pipeline (thread ou enfileira no RQ) |
| `resilience.py` | circuit breaker + timeout + fail-open (sem dependência extra) |
| `../pipelines.py` | os 3 pipelines, agora usando o barramento e a resiliência |
| `../worker.py` | processo worker do RQ (modo redis) |

### Resiliência de LLM (já aplicada)

- **Curso / Youtuber:** chamadas de LLM (quiz, roteiro, segmentação,
  highlights) passam por `guard(...)` com **timeout** e **circuit breaker** por
  provider. Uma chamada pendurada não trava o pipeline para sempre.
- **Tendências:** a síntese (Chain 3, Claude Sonnet) é **fail-open**. Se falhar,
  o job ainda entrega ranking + insights (Chains 1 e 2) — degrade gracioso.

---

## Como rodar

### Modo inline (dev — padrão, sem Redis)

```bash
pip install -r requirements.txt
cp .env.example .env            # preencha OPENAI_API_KEY
python app.py                   # RUN_MODE=inline por padrão
```

Comportamento idêntico ao original. Nada de Redis.

### Modo redis (workers separados) — local

```bash
# 1. suba um Redis (via Docker, por ex.)
docker run -p 6379:6379 redis:7-alpine

# 2. no .env:  RUN_MODE=redis  e  REDIS_URL=redis://localhost:6379/0

# 3. dois processos, em terminais separados:
gunicorn --worker-class gthread --workers 2 --threads 8 --timeout 0 app:app
python worker.py
```

### Modo redis com Docker Compose (um comando)

```bash
cp .env.example .env            # preencha as chaves
docker compose up --build
# escalar os workers separados do web:
docker compose up --build --scale worker=3
```

---

## Verificação

O `_smoke_test.py` exercita a camada `infra/` em modo inline (sem chaves, sem
Redis): fluxo de eventos, replay para assinante atrasado, abertura do circuit
breaker e fail-open.

```bash
python _smoke_test.py
```

---

## Detalhes que importam

- **SSE + gunicorn:** streaming exige workers com threads (`gthread`) ou
  gevent; worker `sync` puro bloqueia. O Dockerfile já usa `gthread`.
- **Whisper no worker:** no modo redis, a transcrição roda no `worker.py`, não
  no web — o web fica leve e stateless.
- **Disco local ainda é o storage.** O próximo passo (Fase 1.b) é mover
  `static/videos` e `output/` para S3/MinIO; enquanto isso, no Compose, web e
  worker compartilham o mesmo build mas **não** o mesmo disco — rode-os na
  mesma máquina/volume ou avance para object storage antes de escalar de fato.
- **Idempotência e graceful shutdown** entram na Fase 2; o RQ já faz warm
  shutdown ao receber SIGTERM.
