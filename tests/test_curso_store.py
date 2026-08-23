"""tests/test_curso_store.py — cobre curso/store.py contra um Postgres
real (usa DATABASE_URL do ambiente, mesmo padrão de tests que já
dependem de Postgres neste projeto). Roda em qualquer schema — cria e
derruba suas próprias tabelas via _ensure_schema()."""

import os
import uuid

import pytest

pytest.importorskip("psycopg2")

if not os.getenv("DATABASE_URL"):
    pytest.skip("DATABASE_URL não configurada — teste precisa de Postgres real",
                allow_module_level=True)

from curso.store import (  # noqa: E402
    CursoStoreError, aprovar_curso, atualizar_manifesto, criar_curso,
    get_curso, get_lesson, get_lesson_content, list_cursos,
    list_lessons_pendentes, save_lesson_content, save_lesson_quiz,
    set_lesson_status,
)


@pytest.fixture
def manifest():
    return {
        "title": "RAG do Zero", "description": "curso sobre RAG", "audience": "estudante",
        "difficulty": "fundamentos", "estimated_duration_min": 60, "style": "pratico",
        "learning_objectives": ["entender RAG"], "prerequisites": [],
        "modules": [
            {"title": "Fundamentos", "objective": "entender embeddings", "lessons": [
                {"title": "O que é embedding", "objective": "explicar embedding",
                 "duration_min": 15, "concepts": ["embedding", "vetor"],
                 "quiz_required": True},
            ]},
            {"title": "RAG na prática", "objective": "implementar RAG", "lessons": [
                {"title": "Chunking", "objective": "explicar chunking", "duration_min": 20,
                 "concepts": ["chunking", "embedding"], "exercise_required": True},
            ]},
        ],
        "knowledge_gaps": [{"descricao": "não explica vector db", "conceito_faltante": "vector database"}],
    }


@pytest.fixture
def user_key():
    # cada teste com um user_key único evita interferência entre testes
    # que rodam contra o mesmo Postgres (não há transação isolando)
    return f"test_user_{uuid.uuid4().hex[:8]}"


def test_criar_e_ler_curso(manifest, user_key):
    curso = criar_curso(user_key, "documento", manifest)
    assert curso["status"] == "aguardando_aprovacao"
    assert "course_id" in curso

    lido = get_curso(curso["course_id"], user_key)
    assert lido["manifest_json"]["title"] == "RAG do Zero"
    assert lido["origem"] == "documento"


def test_isolamento_entre_usuarios(manifest, user_key):
    curso = criar_curso(user_key, "documento", manifest)
    assert get_curso(curso["course_id"], "outro_user_qualquer") is None
    assert list_cursos("outro_user_qualquer") == []
    assert len(list_cursos(user_key)) >= 1


def test_lessons_pendentes_espelha_o_manifest(manifest, user_key):
    curso = criar_curso(user_key, "documento", manifest)
    pendentes = list_lessons_pendentes(curso["course_id"])
    assert len(pendentes) == 2
    assert all(p["status"] == "pendente" for p in pendentes)


def test_set_lesson_status_afeta_so_uma_aula(manifest, user_key):
    curso = criar_curso(user_key, "documento", manifest)
    pendentes = list_lessons_pendentes(curso["course_id"])
    set_lesson_status(pendentes[0]["id"], "concluido", video_url="static/x.mp4")

    ainda_pendentes = list_lessons_pendentes(curso["course_id"])
    assert len(ainda_pendentes) == 1
    assert ainda_pendentes[0]["id"] == pendentes[1]["id"]


def test_editar_manifesto(manifest, user_key):
    curso = criar_curso(user_key, "documento", manifest)
    manifest["title"] = "RAG do Zero — editado"
    editado = atualizar_manifesto(curso["course_id"], user_key, manifest)
    assert editado["title"] == "RAG do Zero — editado"


def test_editar_manifesto_de_outro_usuario_falha(manifest, user_key):
    curso = criar_curso(user_key, "documento", manifest)
    with pytest.raises(CursoStoreError):
        atualizar_manifesto(curso["course_id"], "outro_user", manifest)


def test_aprovar_bloqueia_edicao_subsequente(manifest, user_key):
    """Regressão: bug encontrado e corrigido nesta sessão — editar depois
    de aprovado NÃO estava sendo bloqueado."""
    curso = criar_curso(user_key, "documento", manifest)
    aprovado = aprovar_curso(curso["course_id"], user_key)
    assert aprovado["status"] == "aprovado"

    with pytest.raises(CursoStoreError, match="não pode mais ser editado"):
        atualizar_manifesto(curso["course_id"], user_key, manifest)


def test_get_lesson_valida_dono(manifest, user_key):
    curso = criar_curso(user_key, "documento", manifest)
    lesson_id = list_lessons_pendentes(curso["course_id"])[0]["id"]

    assert get_lesson(lesson_id, user_key) is not None
    assert get_lesson(lesson_id, "outro_user") is None


def test_save_lesson_content_e_quiz_sao_upsert_independentes(manifest, user_key):
    curso = criar_curso(user_key, "documento", manifest)
    lesson_id = list_lessons_pendentes(curso["course_id"])[0]["id"]

    save_lesson_content(lesson_id, explicacao="explicação completa",
                         resumo="resumo", key_takeaways=["a", "b", "c"])
    save_lesson_quiz(lesson_id, quiz=[{"enunciado": "e1"}],
                      flashcards=[{"frente": "f1", "verso": "v1"}])

    conteudo = get_lesson_content(lesson_id)
    assert conteudo["explicacao"] == "explicação completa"  # não foi apagado pelo save_lesson_quiz
    assert conteudo["quiz_json"] == [{"enunciado": "e1"}]
    assert conteudo["flashcards_json"] == [{"frente": "f1", "verso": "v1"}]
