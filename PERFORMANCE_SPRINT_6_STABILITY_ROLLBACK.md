# Performance Sprint 6 — V49 Stability Rollback

## Motivo
A V48 introduziu Smart Cut por stream-copy. Em teste real local o job terminou sem arquivos de clip, embora a UI mostrasse "Clips prontos". Performance não pode comprometer o resultado funcional.

## Decisão
- Smart Cut removido do caminho padrão.
- Corte volta ao caminho comprovado MoviePy + libx264, frame-accurate.
- `CLIP_PIPELINE_WORKERS=1` e `VERTICAL_PRESET=fast` seguem como baseline local.
- Telemetria `cut_item`/`cut_mode` foi preservada.
- Resultado final publica apenas clips que realmente possuem arquivo.
- Se todos os cortes falharem, o pipeline emite `cut:error`, persiste `clip_errors` e a UI não recebe uma lista falsa de clips prontos.

## Princípio
Primeiro estabilidade e resultado correto; otimizações de corte só voltam após um fixture real reproduzir o formato dos vídeos baixados pelo pipeline.
