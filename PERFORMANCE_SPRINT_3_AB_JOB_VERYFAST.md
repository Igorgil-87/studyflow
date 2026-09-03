# Performance Sprint 3 — Job-level telemetry + veryfast A/B

## Motivo
A média histórica do `/obs` misturava vídeos de durações diferentes (ex.: 40 min e 9 min), impedindo comparação confiável. A Sprint 2 também mostrou que `vertical_outro` caiu para poucos segundos e o gargalo real ficou em `vertical_encode`, com CPU próxima de 100%.

## Mudanças
- `/api/observability/pipeline-stages` agora devolve `jobs` e `selected_job`.
- `/obs` permite selecionar uma execução e exibe somente métricas daquele `job_id`.
- etapas repetidas por Short são agregadas com `SUM(duration_ms)` e mostram quantidade + média por item.
- a média histórica continua disponível, mas recolhida e explicitamente marcada como mistura de vídeos diferentes.
- `VERTICAL_PRESET` passa a `veryfast` por padrão para um A/B controlado.
- resolução, FPS, bitrate-alvo, codec, áudio, legenda e `VERTICAL_WORKERS=1` permanecem iguais.
- `VERTICAL_PRESET=fast` restaura o baseline anterior sem mudança de código.
- cada `vertical_encode` registra o preset no campo `detail`.

## Como comparar
1. Rode novamente o MESMO vídeo de ~9 min usado na V45.
2. Abra `/obs` e selecione a nova execução.
3. Compare com a execução V45: `total`, `vertical`, soma de `vertical_encode`, CPU, RAM e tamanho/qualidade visual do arquivo final.
4. Não aumente workers enquanto `vertical_encode` permanecer CPU-bound.

## Critério
Manter `veryfast` se reduzir materialmente o tempo sem degradação visual perceptível para Shorts e sem aumento de tamanho que prejudique o produto. Caso contrário, volte para `fast`.
