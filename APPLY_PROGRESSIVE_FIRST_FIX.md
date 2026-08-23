# YouTube progressive-first fix

## Por que esta mudança existe

Em produção (Hetzner + Decodo residencial + mweb + BgUtils POT), o formato
progressivo `18` foi validado com download real até 100%, enquanto formatos
DASH separados retornaram HTTP 403 em alguns vídeos.

A estratégia agora é:

1. `mweb + PO Token + proxy` continua como base;
2. vídeo prioriza formato `18`;
3. outros formatos progressivos vêm antes de DASH;
4. `web_safari_hls` deixa de ser fallback automático;
5. áudio é extraído do vídeo local com ffmpeg, evitando um segundo download
   do YouTube e reduzindo gasto do proxy e risco de 403;
6. no módulo Curso, se o vídeo não baixar, ainda existe fallback de áudio
   direto para permitir estudo/transcrição;
7. no módulo Youtuber, falha de vídeo encerra cedo porque cortes dependem dele.

## Arquivos alterados

- `tools/video_downloader.py`
- `tools/audio_extractor.py`
- `pipelines.py`

## Deploy

Depois de mergear na `main`:

```bash
docker compose -f docker-compose.prod.yml up -d --build --remove-orphans
```

Acompanhar o job:

```bash
docker compose -f docker-compose.prod.yml logs -f --tail=300 bgutil-pot worker
```

No caminho esperado, o worker deve registrar `progressive_first`, baixar o
vídeo uma única vez e em seguida registrar `Extraindo áudio do vídeo local`.
