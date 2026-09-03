# Performance Sprint 4 — Concorrência controlada por clip

## Objetivo

Testar throughput real com **2 clips em paralelo**, mantendo uma chave simples para retornar a 1 worker. A decisão vem das métricas por job da V46, não de suposição.

## Mudanças

- `CLIP_PIPELINE_WORKERS=2` governa concorrência do corte e do encode vertical.
- As fases continuam separadas: corte termina antes do vertical. Isso evita sobreposição descontrolada entre dois estágios pesados.
- `VERTICAL_PRESET` volta para `fast` como baseline conservador.
- `CUT_PRESET=fast` fica configurável.
- Cada `vertical_encode` registra duração do clip, preset e workers.
- Cada fechamento registra `mode=stream_copy` ou `mode=reencode_fallback` em `vertical_outro_mode`.
- O motivo do fallback fica persistido no resultado do clip e na telemetria.
- A normalização do fechamento usa lock por variante, evitando dois workers gerarem o mesmo arquivo de cache simultaneamente.
- O resultado do corte inclui `duracao_segundos`, permitindo comparar tempo de processamento por segundo de mídia.

## A/B

Baseline:

```env
CLIP_PIPELINE_WORKERS=1
VERTICAL_PRESET=fast
```

Experimento:

```env
CLIP_PIPELINE_WORKERS=2
VERTICAL_PRESET=fast
```

Use o mesmo vídeo e o mesmo número de Shorts. Compare no `/obs` por `job_id`:

- `total`
- `cut`
- `vertical`
- `vertical_encode` total e por item
- CPU média/pico
- RAM mínima livre
- `vertical_outro_mode`

## Critério de decisão

Mantenha 2 workers apenas se o `total` cair de forma consistente sem pressão de memória/swap e sem aumento relevante de falhas. Se CPU ficar permanentemente saturada e o tempo piorar, volte para 1.
