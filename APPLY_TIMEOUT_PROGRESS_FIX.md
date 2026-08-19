# StudyFlow — timeout de vídeo + progresso de renderização

## Causa confirmada em produção

O job Youtuber foi encerrado pelo RQ depois de 1800 segundos enquanto o ffmpeg
continuava renderizando os clips. O pipeline não estava travado: o processo do
ffmpeg estava ativo e consumindo CPU.

## O que mudou

- Jobs comuns continuam com `JOB_TIMEOUT_SECONDS=1800` por padrão.
- O pipeline Youtuber usa `VIDEO_JOB_TIMEOUT_SECONDS=7200` (2 horas) por padrão.
- `dispatch()` aceita timeout por job; em `RUN_MODE=inline` o parâmetro é
  ignorado, mantendo compatibilidade local sem Redis/RQ.
- A UI separa as etapas `Corte`, `Renderização` e `Finalização`.
- O evento `cut=done` agora ocorre assim que os cortes-base existem, antes dos
  encodes pesados do ffmpeg.
- Renderização 9:16 e fechamento passam a informar progresso próprio.

## Configuração

Opcionalmente configure no `.env`:

```env
JOB_TIMEOUT_SECONDS=1800
VIDEO_JOB_TIMEOUT_SECONDS=7200
```

Não é obrigatório adicionar `VIDEO_JOB_TIMEOUT_SECONDS`: 7200 já é o padrão do
código. Em produção Redis/RQ ele controla o timeout do pipeline Youtuber; em
execução local `RUN_MODE=inline` não interfere.

## Deploy

Depois de mergear na `main`:

```bash
docker compose -f docker-compose.prod.yml up -d --build --remove-orphans
```

Durante um teste:

```bash
docker compose -f docker-compose.prod.yml logs -f --tail=300 worker
```

A interface deverá avançar por Corte -> Renderização -> Finalização, em vez de
permanecer visualmente em Corte enquanto o ffmpeg trabalha.
