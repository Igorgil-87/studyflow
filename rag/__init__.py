"""
rag/ — Retrieval-Augmented Generation sobre as transcrições dos vídeos.

Indexa os segmentos transcritos numa BASE VETORIAL (Postgres + pgvector) e
responde perguntas buscando os trechos mais similares e gerando uma resposta
ancorada neles (com timestamps como fonte).

Camada opcional e desacoplada: bibliotecas de banco são importadas de forma
tardia; sem RAG_ENABLED ou sem Postgres, o app roda normalmente.
"""
