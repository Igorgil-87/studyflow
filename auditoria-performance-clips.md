# Auditoria de Performance — Pipeline de Clips/Shorts

> Análise pura, código real lido linha por linha em `pipelines.py`, `tools/video_splitter.py`, `tools/transcriber.py`, `tools/vertical_export.py`, `tools/audio_extractor.py`, `cache/llm_cache.py`. **Nada foi implementado ainda** — é isso que foi pedido.

## Mapa do pipeline (as 5 etapas da tela)

```
Download (áudio+vídeo em paralelo)
  → Transcrição (faster-whisper)
    → IA Viral (LLM identifica highlights, com cache semântico)
      → Corte (MoviePy corta cada highlight)
        → Vertical + legenda (só pra Shorts, ffmpeg)
```

## 1. O que já está bem otimizado (não mexer)

Antes de qualquer crítica — bastante coisa aqui já passou por uma rodada de ajuste séria, com data documentada no próprio código (**30/07/2026**, claramente uma sessão de tuning de performance anterior):

- **Download**: áudio (`bestaudio/best`, stream leve) e vídeo baixados **em paralelo** (`ThreadPoolExecutor(max_workers=2)`) — já correto, e o áudio sendo um stream separado e pequeno não é desperdício, é o desenho certo.
- **Transcrição**: `faster-whisper` (não o Whisper original, bem mais lento), `compute_type="int8"` (quantizado pra CPU), `vad_filter=True` (pula silêncio — ganho real em vídeo com pausa), `word_timestamps=False` (testado e desligado de propósito — ligar isso "deixava o pipeline mega lento" no hardware de 8GB local).
- **Modelo Whisper fica em cache entre vídeos** (`_MODEL_CACHE`), mas é **liberado da RAM** logo depois de usar, exatamente na hora em que o corte de vídeo (a etapa mais pesada em memória) mais precisa de espaço — troca calculada (recarrega o modelo no próximo vídeo, custa alguns segundos; evita swap, que destrói tudo).
- **Vertical export**: `preset="fast"` em vez de `medium`.
- `gc.collect()` chamado explicitamente entre a etapa de corte e o ffmpeg do vertical.
- Tradução de legenda feita **uma vez pra transcrição inteira**, não por clip — resultado mais consistente e mais rápido que a versão anterior (documentado no próprio código).
- **"Cortes" (2-15min) pulam vertical+legenda de propósito** — só Shorts passam por isso, porque o custo do encode escala com a duração e não faz sentido nenhum reenquadrar um vídeo de 15 minutos que não vai ser usado como Short.

## 2. O achado mais importante — e o motivo de eu não sair implementando

```python
# tools/vertical_export.py, chamado de pipelines.py:
# sequencial (max_workers=1), não paralelo: testado e ajustado em 30/07/2026 —
# no hardware de 8GB RAM do usuário, rodar ffmpeg em paralelo causava troca de
# memória pro disco (swap), deixando TUDO mais lento, não só essa etapa.
```

**Paralelismo já foi tentado aqui, medido, e revertido.** Isso muda a análise inteira: não dá pra simplesmente "adicionar `ThreadPoolExecutor`" em qualquer etapa pesada e assumir que vai melhorar — já aconteceu do contrário, documentado com data. Qualquer proposta de paralelismo daqui pra frente **precisa vir com medição real antes**, não só teoria.

**Ponto crítico**: essa decisão foi tomada testando no **Mac local de 8GB** do usuário. O servidor de produção (Hetzner CX43) tem **16GB de RAM e 8 vCPUs** — o dobro de memória, só que também compartilhada com Postgres+Redis+n8n+crawl4ai+bgutil-pot rodando ao mesmo tempo. Não dá pra saber se o mesmo limite (`max_workers=1`) ainda é o certo pra esse ambiente sem medir de verdade lá — pode estar deixando desempenho na mesa, ou pode ser que a soma dos outros serviços já deixe pouca margem mesmo com o dobro de RAM. **Isso não se resolve por dedução, se resolve monitorando.**

## 3. Achados concretos, por impacto provável

### 3.1. Corte de clips (`tools/video_splitter.py`) — maior suspeito de ser "a tela mais lenta"

```python
for i, aula in enumerate(aulas, 1):        # SEQUENCIAL, sem exceção
    video = VideoFileClip(video_path)       # reabre o vídeo do ZERO a cada clip
    clip = video.subclip(inicio, fim)
    clip.write_videofile(..., codec="libx264", preset="fast")  # re-encode completo
```

Três coisas empilhadas aqui:
1. **Nenhum paralelismo** entre os clips — se são 5 highlights, é 5 encodes um atrás do outro.
2. **Reabre o arquivo de vídeo inteiro a cada clip** — decisão deliberada e testada (reaproveitar o mesmo `VideoFileClip` quebra a partir do segundo clip, bug real do MoviePy documentado no código), mas tem custo: reprobe do arquivo inteiro, N vezes.
3. **Re-encode completo via MoviePy/libx264**, não `-c copy` (stream copy). Isso é CPU-bound de verdade — é aqui que o tempo mais escala com quantidade de clips.

Isso é exatamente o mesmo padrão que já foi otimizado (e depois revertido) no vertical export. **Antes de decidir se paraleliza isso**, precisa saber: no servidor de produção, rodando 3-5 encodes libx264 simultâneos, o que acontece com a RAM e o CPU? Só rodando e medindo se sabe — nenhuma das duas respostas (paraleliza / não paraleliza) está certa sem esse dado.

### 3.2. Indexação no RAG bloqueia o pipeline por nada

```python
emit("transcribe", "done", ...)
_maybe_index_rag(video_url, ...)      # SÍNCRONO, bloqueia aqui
emit("highlights", "running", ...)    # só começa depois
```

`_maybe_index_rag` calcula embedding da transcrição inteira e grava no pgvector — usado **só** pela funcionalidade separada de "Pergunte ao vídeo" (RAG chat). **A etapa de IA Viral/Corte não depende desse resultado em nada.** Hoje, se `RAG_ENABLED=1`, o usuário fica esperando essa indexação terminar antes da IA Viral nem começar, sem nenhum motivo funcional — é uma dependência de código, não uma dependência real. Esse é o achado de menor risco pra resolver (rodar em thread separada / depois de emitir o resultado principal), porque não tem histórico de ter dado problema como o paralelismo de ffmpeg — é I/O de rede (chamada de embedding), não CPU/RAM pesada feito ffmpeg.

### 3.3. Cache semântico de LLM existe, mas está desligado por padrão

`cache/llm_cache.py` tem uma implementação sofisticada pronta pra etapa de IA Viral: hash exato + fallback por similaridade de embedding (cosseno ≥ 0.95). Mas:

```python
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "0") == "1"   # default OFF
```
```
# .env.example:
CACHE_ENABLED=0
```

Preciso que você confirme: isso está ligado (`CACHE_ENABLED=1`) no `.env` de produção do Hetzner, ou está desligado como vem por padrão? Se estiver desligado, o cenário onde isso ajuda de verdade (mais comum do que parece): reprocessar a **mesma URL** com os mesmos parâmetros (usuário testa de novo, dá erro no meio e refaz, etc.) paga a chamada de LLM inteira de novo, quando podia ser instantâneo.

### 3.4. Geração de thumbnail — sequencial também, mas provavelmente barata

`_make_thumbnails` também é um `for` sequencial, mas é extração de 1 frame + composição de texto (Pillow), não re-encode de vídeo — deve ser ordens de magnitude mais rápida por item que o corte. Baixa prioridade, citando só pra fechar o mapa completo.

### 3.5. Modelo Whisper "base" — possível experimento, não uma resposta clara

`WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")`. Existe a tentação de trocar pra `tiny` (mais rápido). Mas isso teria efeito duplo: a transcrição serve tanto pra achar os highlights (onde uma transcrição aproximada já basta) quanto pra gerar a legenda queimada no vídeo final (onde precisão importa de verdade pro espectador). Trocar o modelo pode acelerar uma coisa e piorar a outra — não é um "sim" óbvio, é algo pra testar comparando qualidade de legenda antes/depois, não só velocidade.

## 4. O ponto que amarra tudo: falta instrumentação de verdade

Cada decisão de performance que já existe no código (Whisper sem timestamp, vertical sequencial, preset fast) foi tomada testando manualmente numa máquina específica (8GB local), numa data específica (30/07). Isso **funcionou uma vez**, mas não escala como processo — toda vez que uma dessas perguntas aparecer de novo (paraleliza o corte? o servidor aguenta?), a resposta não pode ser "vamos tentar e ver" de novo manualmente.

O projeto já tem a infraestrutura certa pra isso — `obs/tracing.py` e a tabela de observabilidade (usada hoje pra custo/tokens de LLM). **A peça que falta é a mesma instrumentação para os estágios de ffmpeg/vídeo**: duração de cada etapa (download/transcrição/highlights/corte/vertical) e pico de RAM durante cada uma, gravados no mesmo banco, visíveis no `/obs` que já existe.

Só com esse dado real (do servidor de produção, não do Mac local) dá pra responder com confiança:
- O corte de clips vale a pena paralelizar no Hetzner, ou vai repetir o problema do vertical?
- Quanto tempo cada etapa realmente consome, em proporção — pra saber se vale mais a pena atacar o corte, a transcrição, ou outra coisa que nem apareceu aqui?
- O cache de LLM está sendo usado, e quanto ele economiza quando é?

## Minha recomendação de próximo passo

Não é "paraleliza o corte" nem "liga o cache" direto — é **instrumentar primeiro, decidir depois com dado real**. Concretamente, nessa ordem:

1. Confirmar se `CACHE_ENABLED` está ligado em produção (isso você sabe na hora, sem código).
2. Adicionar medição de duração + pico de RAM por etapa (download/transcrição/highlights/corte/vertical), reaproveitando a infra de observabilidade que já existe — baixo risco, não muda comportamento nenhum, só mede.
3. Rodar um vídeo real de teste no Hetzner com isso ligado, olhar os números.
4. Só aí decidir, com dado, se vale paralelizar o corte (e com que grau — talvez 2 workers em vez de tudo de uma vez, não é tudo-ou-nada).
5. Resolver o bloqueio desnecessário do RAG (item 3.2) — esse eu recomendaria fazer independente do resto, baixo risco, ganho garantido.

Quer que eu comece pela instrumentação (item 2), já que é o que destrava a decisão de tudo mais com segurança?
