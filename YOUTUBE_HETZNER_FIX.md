# StudyFlow — YouTube / Hetzner hardening

Atualização preparada para o ambiente headless em VPS/Hetzner.

## O que mudou

- `yt-dlp[default]>=2026.7.4` para instalar o companion `yt-dlp-ejs`.
- Deno 2.3.0 instalado no Dockerfile como runtime JavaScript externo.
- Configuração compartilhada do yt-dlp em `tools/youtube_runtime.py`.
- Diagnóstico em `python -m tools.youtube_doctor`.
- Busca, trends, áudio e vídeo passam a usar a mesma configuração de cookies, proxy, timeout e retries.
- Ordem conservadora no download: sem cookies -> `cookies.txt` -> browser local.
- `COOKIES_FILE` é o caminho recomendado em servidor headless.
- `PROXY_URL` é fallback opcional, não requisito básico.
- Em produção, `cookies.txt` fica em volume Docker compartilhado entre `web` e `worker`.
- Upload de cookies pela UI grava atomicamente no caminho configurado por `COOKIES_FILE`.
- `cookies.txt` foi adicionado ao `.gitignore`.
- Mensagens de erro anti-bot agora incluem diagnóstico local.

## Deploy na Hetzner

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Depois valide o runtime:

```bash
docker compose -f docker-compose.prod.yml exec worker python -m tools.youtube_doctor
```

Para testar metadata de um vídeo explicitamente:

```bash
docker compose -f docker-compose.prod.yml exec \
  -e YOUTUBE_DOCTOR_NETWORK=1 worker \
  python -m tools.youtube_doctor --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Cookies

Em produção o compose define:

```text
COOKIES_FILE=/app/secrets/cookies.txt
```

O volume `youtube_cookies` é montado em `web` e `worker`, então um upload feito pela interface fica disponível para ambos os containers e persiste após recriações.

Não coloque `cookies.txt` no Git.

## Proxy residencial

Deixe `PROXY_URL` vazio inicialmente. Se o `doctor` estiver saudável (Deno/EJS presentes) e o YouTube ainda recusar o IP da Hetzner por anti-bot, configure no `.env`:

```text
PROXY_URL=http://usuario:senha@host:porta
```

Depois recrie `web` e `worker`:

```bash
docker compose -f docker-compose.prod.yml up -d --build web worker
```

## Variáveis novas/relevantes

```text
COOKIES_FILE=
COOKIES_BROWSER=
PROXY_URL=
YOUTUBE_DOCTOR_NETWORK=0
YTDLP_SOCKET_TIMEOUT=30
YTDLP_RETRIES=3
```
