"""tests/test_provenance.py — cobre curso/provenance.py com RAG mockado."""

from unittest.mock import patch

from curso.provenance import montar_material_e_claims


def test_sem_source_doc_id_vira_complementar():
    material, claims = montar_material_e_claims(
        None, "Embeddings", "explicar", ["embedding"], "contexto fallback"
    )
    assert material == "contexto fallback"
    assert len(claims) == 1
    assert claims[0]["tipo"] == "complementar"
    assert claims[0]["doc_id"] is None


def test_rag_desligado_fail_open_vira_complementar():
    with patch("rag.store.get_store", return_value=None):
        material, claims = montar_material_e_claims(
            "material:abc", "Embeddings", "explicar", ["embedding"], "fallback"
        )
    assert claims[0]["tipo"] == "complementar"
    assert material == "fallback"


def test_com_chunks_reais_vira_fonte():
    fake_chunks = [
        {"text": "Embedding é uma representação vetorial.", "start": 0},
        {"text": "Vetores capturam significado semântico.", "start": 1},
    ]
    with patch("rag.store.get_store", return_value=object()), \
         patch("rag.query.search", return_value=fake_chunks), \
         patch("cache.embeddings.embed", return_value=[0.1] * 10):
        material, claims = montar_material_e_claims(
            "material:abc", "Embeddings", "explicar", ["embedding"], "fallback"
        )

    assert len(claims) == 2
    assert all(c["tipo"] == "fonte" for c in claims)
    assert claims[0]["doc_id"] == "material:abc"
    assert claims[0]["chunk_id"] == "0"
    assert "Embedding é uma representação vetorial." in material


def test_erro_no_rag_fail_open():
    with patch("rag.store.get_store", side_effect=RuntimeError("Postgres fora do ar")):
        material, claims = montar_material_e_claims(
            "material:abc", "Aula", "obj", ["c1"], "fallback"
        )
    assert claims[0]["tipo"] == "complementar"
    assert material == "fallback"
