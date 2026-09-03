# StudyFlow — correção BgUtils + proxy residencial

## Causa confirmada

O worker consegue alcançar o serviço `bgutil-pot`, o proxy residencial consegue abrir HTTPS para Google/YouTube e o container do provider consegue acessar diretamente o BotGuard. Porém a versão 1.3.1 oficial do servidor BgUtils apresenta falhas `socket hang up`/503 quando o proxy enviado pelo yt-dlp é usado durante a geração do token.

O upstream PR #247 corrige esse ponto substituindo o fetch via axios por `node:https` com o mesmo `ProxyAgent`. O patch está pinado no commit:

`411d8d6d04a6bcb00108fd16165d2aae213d08a6`

O StudyFlow agora constrói seu próprio container do provider em `infra/bgutil-pot/Dockerfile`, em vez de usar `brainicism/bgutil-ytdlp-pot-provider:1.3.1-deno` diretamente.

## Arquitetura

```text
StudyFlow worker
  └─ yt-dlp
      ├─ PROXY_URL -> Decodo residencial
      ├─ cookies.txt
      ├─ player_client=mweb
      └─ PO Token -> http://bgutil-pot:4416
                         └─ provider patched
                             └─ node:https + ProxyAgent
```

## Deploy

```bash
docker compose -f docker-compose.prod.yml up -d --build --remove-orphans
```

Confirme:

```bash
docker compose -f docker-compose.prod.yml ps
```

`bgutil-pot` deve ficar `healthy`.

Depois:

```bash
docker compose -f docker-compose.prod.yml exec worker python -m tools.youtube_doctor
```

Esperado:

```text
POT plugin ....... OK 1.3.1
POT provider ..... OK
player clients ... mweb
proxy ............ configurado
```

## Teste isolado

```bash
docker compose -f docker-compose.prod.yml exec worker sh -c 'yt-dlp --proxy "$PROXY_URL" --cookies "$COOKIES_FILE" --simulate --verbose "https://www.youtube.com/watch?v=vtvFVH9JdNI"'
```

No log, procure uma geração de token bem-sucedida e ausência de `socket hang up`, `Unable to fetch PO Token` e `HTTP Error 403`.

## Observação

O PR upstream ainda pode estar aberto. Por isso o commit está pinado: o deploy é reproduzível e não depende do conteúdo futuro de uma branch. Quando a correção for incorporada a uma release oficial do provider, podemos voltar a usar uma imagem oficial versionada.
