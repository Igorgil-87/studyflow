"""tests/test_curso_quiz_completo.py — quiz completo (N perguntas) do
Course Engine. Complementa o checkpoint (1 pergunta, Fase 5) — usa a
mesma fonte de dado (quiz_json) e a mesma função de registro
(registrar_tentativa_quiz, Sprint B2), mas corrige no servidor.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="precisa de DATABASE_URL (Postgres)"
)

from curso.store import (
    aprovar_curso, criar_curso, list_lessons_pendentes,
    save_lesson_content, save_lesson_quiz,
)


@pytest.fixture
def client():
    import os as _os
    _os.environ.setdefault("SECRET_KEY", "test")
    _os.environ.setdefault("OPENAI_API_KEY", "sk-fake")
    import app as real_app
    c = real_app.app.test_client()
    with c.session_transaction() as sess:
        sess["logged_in"] = True
        sess["user"] = "quiz_completo_test@studyflow"
    return c


def _curso_com_quiz(user_key="quiz_completo_test@studyflow"):
    manifest = {
        "title": "Curso Quiz", "description": "", "audience": "estudante",
        "difficulty": "fundamentos", "estimated_duration_min": 10, "style": "pratico",
        "learning_objectives": [], "prerequisites": [],
        "modules": [{"title": "M1", "objective": "", "lessons": [
            {"title": "L1", "objective": "", "duration_min": 10, "concepts": []}
        ]}],
    }
    curso = criar_curso(user_key, "documento", manifest)
    course_id = curso["course_id"]
    aprovar_curso(course_id, user_key)
    lesson_id = list_lessons_pendentes(course_id)[0]["id"]
    save_lesson_content(lesson_id, explicacao="c" * 50, resumo="r", key_takeaways=[])
    save_lesson_quiz(lesson_id, quiz=[
        {"enunciado": "1+1?", "alternativas": ["1", "2", "3"], "resposta_correta": "2"},
        {"enunciado": "2+2?", "alternativas": ["3", "4", "5"], "resposta_correta": "4"},
        {"enunciado": "3+3?", "alternativas": ["5", "6", "7"], "resposta_correta": "6"},
    ], flashcards=[])
    return course_id, lesson_id


class TestGetQuizCompleto:
    def test_nao_vaza_resposta_correta(self, client):
        course_id, lesson_id = _curso_com_quiz()
        r = client.get(f"/api/curso2/{course_id}/licoes/{lesson_id}/quiz")
        assert r.status_code == 200
        for pergunta in r.get_json()["perguntas"]:
            assert "resposta_correta" not in pergunta

    def test_aula_sem_quiz_da_404(self, client):
        manifest = {"title": "Sem quiz", "description": "", "audience": "estudante",
            "difficulty": "fundamentos", "estimated_duration_min": 10, "style": "pratico",
            "learning_objectives": [], "prerequisites": [],
            "modules": [{"title": "M1", "objective": "", "lessons": [
                {"title": "L1", "objective": "", "duration_min": 10, "concepts": []}
            ]}]}
        curso = criar_curso("quiz_completo_test@studyflow", "documento", manifest)
        aprovar_curso(curso["course_id"], "quiz_completo_test@studyflow")
        lesson_id = list_lessons_pendentes(curso["course_id"])[0]["id"]
        save_lesson_content(lesson_id, explicacao="c" * 50, resumo="r", key_takeaways=[])
        r = client.get(f"/api/curso2/{curso['course_id']}/licoes/{lesson_id}/quiz")
        assert r.status_code == 404


class TestResponderQuizCompleto:
    def test_corrige_no_servidor_mesmo_se_cliente_tentar_forjar(self, client):
        """O ponto central: o cliente manda uma resposta 'forjada' pra
        uma pergunta e o servidor NÃO aceita — corrige contra o
        resposta_correta real guardado no banco, não confia no cliente."""
        course_id, lesson_id = _curso_com_quiz()
        r = client.post(
            f"/api/curso2/{course_id}/licoes/{lesson_id}/quiz/responder",
            json={"respostas": ["2", "resposta-forjada-que-nao-existe", "6"]},
        )
        d = r.get_json()
        assert r.status_code == 200
        assert d["acertos"] == 2
        assert d["resultados"][1]["correto"] is False
        assert d["resultados"][1]["resposta_correta"] == "4"  # só revela depois de responder

    def test_numero_errado_de_respostas_da_400(self, client):
        course_id, lesson_id = _curso_com_quiz()
        r = client.post(
            f"/api/curso2/{course_id}/licoes/{lesson_id}/quiz/responder",
            json={"respostas": ["2", "4"]},  # faltando 1
        )
        assert r.status_code == 400

    def test_resultado_fica_registrado_em_quiz_attempts(self, client):
        from curso.store import _connect
        course_id, lesson_id = _curso_com_quiz()
        client.post(
            f"/api/curso2/{course_id}/licoes/{lesson_id}/quiz/responder",
            json={"respostas": ["2", "4", "6"]},  # todas certas
        )
        conn = _connect()
        try:
            with conn.cursor() as c:
                c.execute(
                    "SELECT total_perguntas, acertos FROM quiz_attempts WHERE lesson_id=%s",
                    (lesson_id,),
                )
                row = c.fetchone()
        finally:
            conn.close()
        assert row == (3, 3)

    def test_isolamento_entre_usuarios(self, client):
        course_id, lesson_id = _curso_com_quiz()
        import app as real_app
        client2 = real_app.app.test_client()
        with client2.session_transaction() as sess:
            sess["logged_in"] = True
            sess["user"] = "outro_usuario_quiz"
        r = client2.post(
            f"/api/curso2/{course_id}/licoes/{lesson_id}/quiz/responder",
            json={"respostas": ["2", "4", "6"]},
        )
        assert r.status_code == 404
