# Performance Sprint 5 — Smart Cut + Whisper Profiling (V48)

## Hipóteses encerradas
- `CLIP_PIPELINE_WORKERS=2` saturou CPU local e piorou o total; default volta a 1.
- `VERTICAL_PRESET=fast` volta a ser baseline estável.

## Smart Cut
`VideoSplitterTool` tenta primeiro cortar com ffmpeg stream-copy (`-c copy`).
Se ffmpeg falhar ou a duração resultante ficar fora da tolerância, o sistema cai
automaticamente no comportamento anterior com MoviePy/libx264.

Telemetria nova por clip:
- `cut_item`: tempo real do corte.
- `cut_mode`: `mode=stream_copy` ou `mode=reencode`, com razão do fallback.

Flags:
- `SMART_CUT=1`
- `SMART_CUT_DURATION_TOLERANCE_SEC=0.75`
- `CLIP_PIPELINE_WORKERS=1`

## Whisper
A etapa `transcribe` foi decomposta em:
- `whisper_model_load`
- `whisper_inference`
- `whisper_serialize`

O modelo passa a ficar em cache entre jobs por padrão (`WHISPER_RELEASE_AFTER_TRANSCRIBE=0`).
Em host com RAM apertada, configure `WHISPER_RELEASE_AFTER_TRANSCRIBE=1`.

## Próximo teste
Use o mesmo vídeo de ~9 min. No `/obs`, selecione somente o job V48 e compare:
`total`, `cut`, `cut_item`, `cut_mode`, `transcribe`, `whisper_model_load`,
`whisper_inference`, `vertical` e `vertical_encode`.
