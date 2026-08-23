# Deploy do AI Course Generation Engine — passo a passo

Cobre as 5 fases (tudo que está em `ai-course-engine-completo.zip`). Siga
na ordem — cada passo depende do anterior.

## 0. Isto é feito pra rodar no seu servidor cloud (Hetzner), não local

Todo o roteiro abaixo assume o `docker-compose.prod.yml` de produção — os
mesmos containers `web`/`worker`/`scheduler`/`postgres`/`redis`/`n8n`/
`crawl4ai`/`bgutil-pot` que você já tem no ar em studyflow.vip. Nada
disso muda: é uma atualização de código dentro da infra que já existe,
não uma infra nova.

Dois bugs de "container separado" que só existem em produção (não
aparecem rodando local com 1 container só) — **já corrigidos** nos
`docker-compose.*.yml` deste pacote:

1. **Faltava o volume `audios_data`**. O áudio (Fase 4 — "Ouvir aula" e
   Podcast) é gerado no `worker`, mas quem serve o arquivo pro navegador
   é o `web` — exatamente o mesmo problema que resolvemos antes pro
   `/obs` (custo) e pro certificado. Sem esse volume, o áudio geraria
   normalmente, mas o player na tela ficaria com erro 404. Corrigido nos
   3 compose files (dev/full/prod).
2. **O job de vídeo por aula não usava o timeout estendido**. Vídeo com
   várias cenas (TTS + ffmpeg por cena) ia cair no timeout padrão de 30
   minutos em vez do timeout de 2h que o projeto já reserva pra job de
   vídeo pesado (mesmo usado pelo módulo Estúdio). Corrigido em `app.py`.

## 1. Aplicar os arquivos no seu repositório

Extraia o zip e copie por cima da estrutura atual do `youtube-study-agent`:

```bash
unzip ai-course-engine-completo.zip
cd ai-course-engine-completo

# copia tudo por cima do seu projeto (ajuste o caminho de destino)
cp -r curso /caminho/do/seu/projeto/youtube-study-agent/
cp app.py requirements.txt /caminho/do/seu/projeto/youtube-study-agent/
cp docker-compose.yml docker-compose.full.yml docker-compose.prod.yml /caminho/do/seu/projeto/youtube-study-agent/
cp rag/document_extractor.py /caminho/do/seu/projeto/youtube-study-agent/rag/
cp tools/quiz_generator.py /caminho/do/seu/projeto/youtube-study-agent/tools/
cp static/css/style.css /caminho/do/seu/projeto/youtube-study-agent/static/css/
cp templates/*.html /caminho/do/seu/projeto/youtube-study-agent/templates/
cp tests/*.py /caminho/do/seu/projeto/youtube-study-agent/tests/
```

**Se você já editou `app.py`, `requirements.txt`, `docker-compose.prod.yml`
ou `style.css` desde a última entrega minha**, não copie por cima
cegamente — dê um `diff` primeiro, porque esse `cp` sobrescreve sem
avisar. O `docker-compose.prod.yml` em especial: se você mudou algo nele
recentemente (por exemplo mais alguma correção manual), compare antes —
a mudança que importa aqui é só a adição do volume `audios_data`.

## 2. Variável de ambiente — a única obrigatória que falta

```
ANTHROPIC_API_KEY=sk-ant-...
```

Sem ela, todos os agentes do Course Engine (Curriculum, Lesson, Storyboard,
Podcast, Tutor, Exercise) falham logo de cara — é a peça que você disse
que ainda ia criar. Todas as outras variáveis (`COURSE_ENGINE_MODEL` etc.)
já têm default e são opcionais.

## 3. Confirmar a fundação que já existia (não é novo, mas é pré-requisito)

- `DATABASE_URL` configurada e o Postgres de pé — o schema novo
  (`courses`, `modules`, `lessons`, etc.) é criado sozinho na primeira
  chamada, não precisa rodar migração manual.
- O volume `obs_data` que corrigimos antes — sem ele, você não vai
  conseguir ver o custo desses agentes novos em `/obs`.
- `RAG_ENABLED=1` no `.env`, se quiser que o Modo Criativo funcione com
  provenance de verdade (senão tudo cai em "complementar").
- Depois do `up -d`, confirme que os volumes novos foram criados:
  `docker volume ls | grep -E "audios_data|obs_data"` — os dois devem
  aparecer.

### Um ponto que eu não consigo verificar remotamente: nginx

Se o seu servidor usa nginx na frente do Flask servindo `/static/`
**diretamente do disco** (bypassando o container, por performance — não
vi config de nginx neste repositório, então não sei se é o seu caso),
o nginx também precisa enxergar o volume `audios_data` (e o `videos_data`,
que já deveria estar funcionando). Se depois do deploy o vídeo tocar mas
o áudio der 404 mesmo com o volume Docker certo, é sinal de que o nginx
está servindo de um caminho que não é o volume — vale conferir o
`root`/`alias` da location de `/static/` na config dele.

## 4. Rebuild e sobe

```bash
docker compose -f docker-compose.prod.yml build web worker
docker compose -f docker-compose.prod.yml up -d
```

`edge-tts` (novo no `requirements.txt`) é só uma lib Python — não precisa
de nada extra no Dockerfile, o `ffmpeg` que ele depende já está instalado
(confirmamos isso já faz um tempo).

## 5. Confirmar que o servidor alcança o TTS (ponto que eu NÃO consegui testar)

Isso é importante — no meu ambiente de teste a rede não alcançava o
serviço de TTS da Microsoft, então nunca testei narração de verdade,
só simulada. Do seu servidor:

```bash
docker compose -f docker-compose.prod.yml exec web python3 -c "
import asyncio, edge_tts
async def t():
    c = edge_tts.Communicate('teste', 'pt-BR-AntonioNeural')
    await c.save('/tmp/teste.mp3')
asyncio.run(t())
print('OK, TTS funcionou')
"
```

Se der erro de conexão, o egress do servidor pra `speech.platform.bing.com`
está bloqueado — precisa liberar essa saída (é HTTPS normal, porta 443).

## 6. Teste manual guiado (nessa ordem — cada fase depende da anterior)

1. `/curso` → aba **Modo Criativo** → sobe um documento pequeno de teste
   → confirma que o manifesto vem com módulos/aulas fazendo sentido
   (é aqui que você valida o Claude de verdade pela primeira vez).
2. Na tela de revisão, edita algo, salva, **aprova**.
3. "Gerar conteúdo desta aula" — confirma que a explicação faz sentido
   e não é só um resumo raso do documento.
4. "🎬 Gerar vídeo desta aula" — acompanha o progresso via SSE, espera
   terminar, **assiste o vídeo** (é aqui que o TTS real entra em ação
   pela primeira vez de verdade).
5. "🎧 Ouvir aula" e "🎙 Gerar podcast" — confirma os dois áudios.
6. "📝 Gerar exercício" → escreve uma resposta de teste → confirma que
   a avaliação da IA faz sentido.
7. O checkpoint ("Antes de continuar...") deve aparecer sozinho embaixo
   do quiz — erra de propósito uma vez pra ver se o tutor responde com
   uma explicação alternativa.
8. Digite algo no "💬 Pergunte ao Professor" — testa também um comando
   tipo "explique de forma mais simples".
9. `/curso2/<id>/glossario` e `/curso2/<id>/mapa-mental` — confirma que
   carregam e que o mapa mental tem link clicável pra aula.

## 7. Se algo falhar

Toda rota nova retorna erro em JSON com mensagem legível (não 500 cru) —
abra o Network do navegador e leia o `error` da resposta primeiro. Se
precisar de log de servidor, procure por `[curso2]`, `[provenance]` ou
o nome do agente (ex: `CurriculumAgentError`) — são as tags que uso nos
prints de erro tratado.

## 8. O que ainda fica de fora dessa entrega

- Cena de vídeo tipo "footage" (exemplo real, não diagrama) — cai no
  mesmo renderer de diagrama por enquanto, documentado como TODO no
  código (`curso/video_render.py`).
- Adaptive Learning / Knowledge Profile / Study Mode — não fazem parte
  das 5 fases que construí até agora (não estavam no escopo pedido nesta
  rodada de "fase 5").
