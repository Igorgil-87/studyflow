# Performance Sprint 1 — Medição confiável + caminho crítico

Base: `youtube-study-agent(20260901-205754).zip` + `auditoria-performance-clips.md`.

## Objetivo

Melhorar performance sem repetir otimizações por intuição. Esta sprint **não paraleliza ffmpeg/corte**. Ela corrige a qualidade da medição e remove dependência auxiliar do caminho crítico de forma compatível com inline e Redis/RQ.

## O que já existia na base recebida e foi preservado

- download de áudio + vídeo em paralelo;
- faster-whisper int8 + VAD e liberação do modelo antes dos encodes;
- vertical sequencial (`max_workers=1`) por decisão anterior medida em máquina de 8 GB;
- `preset=fast`;
- tradução da transcrição uma vez só;
- cortes longos sem vertical/legenda;
- `pipeline_stages`, `medir_etapa(...)` e painel `/obs`;
- tentativa de tirar o RAG do caminho crítico usando thread daemon.

## Correções desta sprint

### 1. RAM agora inclui subprocessos ffmpeg

A medição anterior usava somente `psutil.Process().memory_info().rss`, isto é, o RSS do processo Python. MoviePy/ffmpeg executa boa parte do trabalho pesado em **processos filhos**, então justamente `cut` e `vertical` podiam aparecer com RAM artificialmente baixa.

A telemetria v2 soma o RSS de:

`worker Python + filhos recursivos (ffmpeg e afins)`

Também registra:

- menor RAM disponível no host durante a etapa;
- maior pressão de memória do host;
- CPU global média e pico;
- duração wall-clock.

CPU global foi escolhida porque o Hetzner compartilha os vCPUs com Postgres, Redis, n8n e demais serviços. Para decidir se há espaço para mais workers, importa a pressão real do host, não só o processo do encoder.

### 2. Compatibilidade com histórico

`measurement_version=2` foi adicionado de forma aditiva. Linhas antigas ficam v1. O agregado de RAM usa somente v2, para não misturar:

- v1 = RSS só do Python;
- v2 = process-tree RSS.

Duração histórica continua válida.

### 3. Latência end-to-end

O pipeline Youtuber agora mede também `stage=total`, que representa a espera completa percebida pelo usuário.

Foram adicionadas medições para lacunas que antes não apareciam claramente:

- `caption_translate`;
- `thumbnails`;
- `outro` para cortes longos;
- `rag_index_async`;
- além de download/transcribe/highlights/cut/vertical já existentes.

### 4. RAG realmente fora do caminho crítico em produção

A base recebida usava `threading.Thread(..., daemon=True)` depois da transcrição. Isso funciona em inline, mas é frágil com RQ: o work-horse pode terminar e matar a daemon thread antes do pgvector acabar.

Agora a indexação usa `infra.dispatch`:

- `RUN_MODE=inline` → thread em background;
- `RUN_MODE=redis` → job RQ separado e durável.

O pipeline de clips não espera o embedding/indexação.

### 5. Cache ficou observável; sem mudança silenciosa de comportamento

No código recebido, `.env` e exemplos estão com `CACHE_ENABLED=0`. A sprint **não liga o cache automaticamente**, pois a auditoria pediu primeiro medição real.

O `/obs` agora mostra explicitamente se o cache está ligado e se é exato ou semântico.

Também foi corrigido um desalinhamento: `CACHE_SEMANTIC` já existia nos exemplos de ambiente, mas `cache/llm_cache.py` não respeitava a flag. Agora:

- `CACHE_ENABLED=1, CACHE_SEMANTIC=0` → somente hash exato; nenhum embedding em cache miss;
- `CACHE_ENABLED=1, CACHE_SEMANTIC=1` → exato + similaridade semântica;
- `CACHE_ENABLED=0` → comportamento anterior, sem cache.

## Como decidir o próximo passo no Hetzner

Rodar pelo menos 3–5 vídeos representativos por formato e observar `/obs`:

1. `total`: latência real do usuário;
2. `cut` e `vertical`: tempo, process-tree RAM, CPU e memória livre;
3. se CPU estiver saturada, mais workers provavelmente não ajudam;
4. se houver CPU ociosa **e** memória livre consistente, fazer benchmark controlado com `2 workers`, não saltar para 5;
5. comparar tempo total e pico de memória antes/depois;
6. reverter se houver swap, degradação de outras aplicações ou piora do p95.

Nenhum grau de paralelismo foi alterado nesta sprint.

## Arquivos principais

- `obs/stage_timer.py`
- `obs/db.py`
- `pipelines.py`
- `cache/llm_cache.py`
- `app.py`
- `templates/obs.html`
- `.env.example`
- `.env.production.example`
- `_performance_instrumentation_test.py`
- `_performance_sprint1_test.py`
- `_cache_exact_mode_test.py`
