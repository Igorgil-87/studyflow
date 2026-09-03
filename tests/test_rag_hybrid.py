"""tests/test_rag_hybrid.py — Sprint A3 da busca híbrida no RAG.

Testa com Postgres real (pgvector) que a fusão (RRF) realmente resgata
um termo técnico exato que a busca vetorial sozinha erraria — não só
que o código roda sem exceção.
"""

import os

import pytest

from rag.hybrid import reciprocal_rank_fusion, search_hibrida
from rag.store import InMemoryStore

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="precisa de DATABASE_URL (Postgres com pgvector)"
)


def _store_pg():
    from rag.store import PgVectorStore
    dsn = os.environ["DATABASE_URL"]
    store = PgVectorStore(dsn, dim=8, table="rag_chunks_test_hybrid")
    with store.conn.cursor() as c:
        c.execute(f"TRUNCATE {store.table}")
    return store


class TestReciprocalRankFusion:
    def test_chunk_no_topo_das_duas_listas_fica_no_topo_fundido(self):
        a = {"video_id": "v1", "start": 10, "text": "a"}
        b = {"video_id": "v1", "start": 20, "text": "b"}
        fundido = reciprocal_rank_fusion([[a, b], [a, b]])
        assert fundido[0]["video_id"] == "v1" and fundido[0]["start"] == 10

    def test_chunk_so_encontrado_numa_lista_ainda_aparece(self):
        a = {"video_id": "v1", "start": 10, "text": "a"}
        b = {"video_id": "v1", "start": 20, "text": "b"}
        fundido = reciprocal_rank_fusion([[a], [b]])
        chaves = {(f["video_id"], f["start"]) for f in fundido}
        assert (("v1", 10) in chaves) and (("v1", 20) in chaves)

    def test_lista_vazia_nao_quebra(self):
        assert reciprocal_rank_fusion([[], []]) == []


class TestSearchHibridaComPostgresReal:
    def test_termo_exato_e_resgatado_mesmo_quando_vetor_erra(self):
        """Cenário central da Sprint A3: um chunk tem o termo técnico
        exato ("BGUTIL_COMMIT") que o usuário busca, mas o embedding
        (fake, controlado no teste) deliberadamente aponta pra OUTRO
        chunk como mais 'semanticamente' próximo. A busca vetorial pura
        erraria; a híbrida precisa resgatar o certo pelo BM25."""
        store = _store_pg()

        # embedding do chunk 1 é ortogonal ao da query -> vetor não acha
        chunk_certo_texto = "o parametro BGUTIL_COMMIT fixa a versao do provider"
        chunk_errado_texto = "explicacao geral sobre configuracao de ambiente"
        store.add([
            {"video_id": "doc1", "start": 0.0, "end": 5.0,
             "text": chunk_certo_texto, "embedding": [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
            {"video_id": "doc1", "start": 10.0, "end": 15.0,
             "text": chunk_errado_texto, "embedding": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
        ])

        query = "BGUTIL_COMMIT"
        # embedding da query aponta pro chunk ERRADO de propósito —
        # simula a busca vetorial "errando" por causa de like/significado
        embed_fn_que_erra = lambda q: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        # confirma a premissa: busca vetorial PURA erra mesmo (acha o errado primeiro)
        so_vetor = store.search(embed_fn_que_erra(query), top_k=1)
        assert so_vetor[0]["text"] == chunk_errado_texto, "premissa do teste furou: vetor deveria errar aqui"

        # busca hibrida real: deve resgatar o certo via BM25
        resultado = search_hibrida(query, embed_fn_que_erra, store, top_k=1)
        assert resultado[0]["text"] == chunk_certo_texto

    def test_store_sem_search_bm25_cai_pra_vetor_puro_sem_quebrar(self):
        """Compatibilidade: um store antigo/mock sem search_bm25 (ex:
        algum teste legado que criava um stub simples) continua
        funcionando, só sem o benefício da fusão."""
        class StoreAntigaSemBM25:
            def search(self, qv, top_k=5, video_id=None):
                return [{"video_id": "v1", "start": 0, "end": 1, "text": "x", "score": 0.9}]

        resultado = search_hibrida("qualquer coisa", lambda q: [0.1], StoreAntigaSemBM25(), top_k=1)
        assert resultado[0]["text"] == "x"

    def test_in_memory_store_search_bm25_encontra_por_substring(self):
        store = InMemoryStore()
        store.add([
            {"video_id": "v1", "start": 0, "end": 1, "text": "python e flask", "embedding": [1, 0]},
            {"video_id": "v1", "start": 5, "end": 6, "text": "javascript e react", "embedding": [0, 1]},
        ])
        resultado = store.search_bm25("flask", top_k=5)
        assert len(resultado) == 1 and "flask" in resultado[0]["text"]
