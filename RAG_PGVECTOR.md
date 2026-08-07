# Base vetorial + RAG (Postgres + pgvector)

Indexa as transcrições dos vídeos numa **base vetorial** (Postgres + pgvector) e
responde perguntas buscando os trechos mais similares e gerando uma resposta
**ancorada** neles, citando os timestamps.

```
transcrição → chunks (rag/chunker) → embeddings → pgvector (rag/store)
pergunta → embedding → busca por cosseno (top-k) → resposta do LLM com fontes
```

Camada opcional e fail-open: sem `RAG_ENABLED` ou sem Postgres, o app roda
normalmente — a indexação é ignorada e a tela avisa.

| Componente | Arquivo |
|---|---|
| Chunking dos segmentos | `rag/chunker.py` |
| Base vetorial (pgvector + fallback em memória) | `rag/store.py` |
| Indexação | `rag/index.py` |
| Busca + resposta ancorada | `rag/query.py` |
| Endpoint | `POST /api/rag/query` |
| Tela | `/rag` ("Pergunte ao vídeo") |

---

## 1. Subir o Postgres com pgvector

A imagem `pgvector/pgvector` já vem com a extensão. Via Docker Compose (já
configurado, com o serviço `postgres`):

```bash
docker compose up -d postgres
```

Ou avulso:

```bash
docker run -d --name pgvector -p 5432:5432 \
  -e POSTGRES_USER=studyflow -e POSTGRES_PASSWORD=studyflow \
  -e POSTGRES_DB=studyflow pgvector/pgvector:pg16
```

A tabela e o índice são criados automaticamente (`rag/store.py::_ensure`); o
`db/init_pgvector.sql` faz o mesmo, caso prefira inicializar pelo banco.

## 2. Ligar o RAG

No `.env`:

```properties
RAG_ENABLED=1
DATABASE_URL=postgresql://studyflow:studyflow@localhost:5432/studyflow
```

Instale o driver (já está no requirements):

```bash
pip install psycopg2-binary
```

## 3. Indexar

Com o RAG ligado, **todo vídeo processado no módulo Youtuber é indexado**
automaticamente após a transcrição (aparece "N trechos indexados na base
vetorial" na timeline). Gere um ou dois vídeos para popular a base.

## 4. Perguntar

Abra **http://localhost:5000/rag**, digite uma pergunta e veja a resposta com as
**fontes (timestamps)** e o score de similaridade de cada trecho. Opcionalmente,
cole a URL de um vídeo para restringir a busca a ele.

A geração da resposta passa pelo tracing → custo/latência aparecem no `/obs`.

---

## Detalhe técnico

- Embeddings: `text-embedding-3-small` (1536 dimensões), reaproveitando
  `cache/embeddings.py`.
- Distância: cosseno (`<=>` do pgvector) com índice `ivfflat`.
- Chunking: junta segmentos até `RAG_CHUNK_CHARS` (600) ou `RAG_CHUNK_SECONDS`
  (60), preservando os timestamps.

## O que está testado

`_rag_test.py` valida, sem Postgres (com uma store em memória de mesma
interface + embeddings falsos): o chunking, a indexação, a busca por
similaridade (recupera o trecho certo), o filtro por vídeo, a resposta ancorada
com fontes, e o fail-open quando não há base.

```bash
python _rag_test.py
```

> Transparência: a camada pgvector (`PgVectorStore`) foi escrita e revisada, mas
> a conexão real com o Postgres precisa ser exercitada na sua máquina — o
> ambiente onde o código foi gerado não roda Postgres. A **lógica** (chunking,
> ranqueamento, montagem do RAG) está coberta por testes; o caminho de banco
> você valida ao subir o Postgres e indexar o primeiro vídeo.

## Próximo passo honesto

Hoje a indexação não deduplica: reprocessar o mesmo vídeo insere os chunks de
novo. O passo natural é uma chave única (`video_id` + `start`) com `ON CONFLICT
DO NOTHING`, ou limpar os chunks do vídeo antes de reindexar.
