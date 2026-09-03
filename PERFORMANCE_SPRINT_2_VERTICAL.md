# Performance Sprint 2 — Vertical deep profiling + eliminação do segundo encode

Base: V44 + métricas locais reais coletadas em `/obs`.

## Evidência que motivou a sprint

Baseline observado:
- `youtuber.total`: ~1103,7 s média;
- `youtuber.vertical`: ~535,3 s média;
- `youtuber.transcribe`: ~128,0 s;
- `youtuber.cut`: ~57,5 s.

A etapa vertical domina a latência percebida. Antes de aumentar workers, esta sprint reduz trabalho redundante e abre a caixa-preta da etapa.

## Causa estrutural encontrada

O Short passava por dois encodes H.264 completos:

1. `vertical_export.py`: reenquadra 9:16 + queima legenda + encode H.264;
2. `video_concat.py`: para anexar poucos segundos de fechamento, o método antigo redimensionava e **reencodava novamente todo o Short**.

Isso faz o custo de anexar um fechamento crescer com a duração inteira do Short.

## Otimizações

### 1. Fast outro concat

`video_concat.append_outro()` agora:
1. normaliza o fechamento para resolução/áudio do Short;
2. guarda essa variante em `static/video/.cache`;
3. concatena com `ffmpeg -c copy`, sem reencodar o Short;
4. se houver incompatibilidade, volta automaticamente ao reencode antigo.

Flag: `OUTRO_FAST_CONCAT=1`.

### 2. Fundo blur barato

O foreground continua em resolução cheia 1080x1920. Apenas o fundo, que será propositalmente desfocado, é processado em 270x480, recebe blur e depois é ampliado. Isso reduz aproximadamente 16x a quantidade de pixels processados pelo boxblur sem baixar a resolução do conteúdo principal.

Flag: `VERTICAL_FAST_BLUR=1`.

### 3. Deep profiling

Além de `vertical`, agora `/obs` separa:
- `vertical_subtitles`;
- `vertical_encode`;
- `vertical_outro`.

Assim a próxima decisão (preset, workers, codec ou outro) passa a ter evidência direta.

## O que NÃO mudou

- `VERTICAL_WORKERS` continua 1;
- resolução continua 1080x1920;
- H.264/yuv420p/30fps continuam iguais;
- bitrate alvo continua 10 Mbps / max 16 Mbps;
- legenda continua queimada;
- `VERTICAL_PRESET` continua `fast` por padrão;
- fallback preserva compatibilidade se stream-copy não funcionar.

## Próximo benchmark

Rodar o mesmo vídeo usado no baseline e comparar:
- `total`;
- `vertical`;
- `vertical_encode`;
- `vertical_outro`;
- CPU média/pico;
- RAM mínima disponível.

Se `vertical_outro` cair para poucos segundos e `vertical_encode` continuar dominante, o próximo experimento deve ser `VERTICAL_PRESET=veryfast` em A/B antes de qualquer aumento de workers.
