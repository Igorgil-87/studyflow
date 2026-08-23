"""tests/test_mindmap.py — cobre curso/mindmap.py (função pura, sem LLM)."""

from curso.mindmap import build_mind_map


def _manifest():
    return {
        "title": "RAG do Zero",
        "modules": [{
            "title": "M1",
            "lessons": [
                {"title": "Embeddings", "concepts": ["embedding", "vetor"]},
                {"title": "Chunking", "concepts": ["chunking", "embedding"]},
            ],
        }],
    }


def _lessons_reais():
    return [
        {"id": "uuid-1", "titulo": "Embeddings"},
        {"id": "uuid-2", "titulo": "Chunking"},
    ]


def test_estrutura_basica():
    grafo = build_mind_map(_manifest(), _lessons_reais())
    tipos = [n["type"] for n in grafo["nodes"]]
    assert tipos.count("course") == 1
    assert tipos.count("module") == 1
    assert tipos.count("lesson") == 2
    assert tipos.count("concept") == 3  # embedding não duplica dentro do módulo


def test_lesson_id_real_resolvido():
    grafo = build_mind_map(_manifest(), _lessons_reais())
    lesson_nodes = {n["label"]: n["lesson_id"] for n in grafo["nodes"] if n["type"] == "lesson"}
    assert lesson_nodes["Embeddings"] == "uuid-1"
    assert lesson_nodes["Chunking"] == "uuid-2"


def test_lesson_sem_id_real_fica_none():
    """Aula do manifest que não bate com nenhuma lesson real (título
    editado depois de gerar, por exemplo) não quebra — só fica sem link."""
    grafo = build_mind_map(_manifest(), [])
    lesson_nodes = [n for n in grafo["nodes"] if n["type"] == "lesson"]
    assert all(n["lesson_id"] is None for n in lesson_nodes)


def test_edges_conectam_curso_modulo_aula_conceito():
    grafo = build_mind_map(_manifest(), _lessons_reais())
    edges_from_course = [e for e in grafo["edges"] if e["from"] == "course"]
    assert len(edges_from_course) == 1  # só 1 módulo

    edges_from_module = [e for e in grafo["edges"] if e["from"] == "module-0"]
    assert len(edges_from_module) == 2  # 2 aulas
