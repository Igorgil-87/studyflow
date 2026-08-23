# StudyFlow — YouTube / Hetzner hardening + PO Token

Atualização para produção headless em VPS/Hetzner.

## Arquitetura atual

```text
StudyFlow worker
  -> yt-dlp + Deno/EJS
  -> cookies.txt (quando necessário)
  -> proxy residencial (PROXY_URL)
  -> BgUtils PO Token Provider
  -> YouTube
```

O proxy residencial e o PO Token resolvem problemas diferentes:

- `PROXY_URL` evita o bloqueio anti-bot associado à reputação do IP de datacenter.
- o PO Token Provider atende formatos GVS que podem retornar `HTTP 403` mesmo depois que metadata e anti-bot já funcionam.

## O que mudou nesta versão

- `bgutil-ytdlp-pot-provider==1.3.1` instalado junto do aplicativo.
- serviço Docker interno `bgutil-pot` usando a imagem `brainicism/bgutil-ytdlp-pot-provider:1.3.1-deno`.
- `YTDLP_POT_PROVIDER_URL=http://bgutil-pot:4416` em `web` e `worker`.
- clientes preferidos `mweb,web_safari,default`.
- fallback explícito `web_safari/HLS` para áudio e vídeo.
- `youtube_doctor` mostra plugin, provider, conectividade e clients.
- erros HTTP 403 agora são classificados separadamente do anti-bot.
- cookies de browser não são tentados quando existe `cookies.txt` válido.

## Deploy

Depois do merge na `main`:

```bash
cd /opt/studyflow/studyflow
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build --remove-orphans
```

Valide:

```bash
docker compose -f docker-compose.prod.yml exec worker python -m tools.youtube_doctor
```

Esperado em produção:

```text
JS runtime ....... OK
cookies.txt ...... OK
cookies browser .. não configurado
proxy ............ configurado
POT plugin ....... OK 1.3.1
POT provider ..... OK  alcançável pela rede Docker
player clients ... mweb,web_safari,default
```

Para testar metadata com a mesma configuração do app:

```bash
docker compose -f docker-compose.prod.yml exec \
  -e YOUTUBE_DOCTOR_NETWORK=1 worker \
  python -m tools.youtube_doctor --url "https://www.youtube.com/watch?v=VIDEO_ID"
```

## `.env`

Em produção mantenha, por exemplo:

```text
COOKIES_BROWSER=
COOKIES_FILE=/app/secrets/cookies.txt
PROXY_URL=http://usuario:senha@host:porta
YTDLP_POT_PROVIDER_URL=http://bgutil-pot:4416
YTDLP_PLAYER_CLIENTS=mweb,web_safari,default
YTDLP_SOCKET_TIMEOUT=30
YTDLP_RETRIES=3
```

Nunca versione `.env`, `cookies.txt` ou credenciais do proxy.

## Observação

PO Token não é garantia universal contra 403. O YouTube muda enforcement continuamente. A estratégia desta versão combina provider recomendado, proxy residencial e fallback HLS para reduzir dependência de um único caminho.
