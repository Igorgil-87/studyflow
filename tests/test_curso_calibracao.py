"""tests/test_curso_calibracao.py — Sprint B1+B2 da calibração
previsão-vs-realidade, estendida ao Course Engine (Growth já tinha algo
parecido; aqui é a versão pro Exercise/Tutor Agent).
"""

import os
import time

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="precisa de DATABASE_URL (Postgres)"
)

from curso.store import (
    CursoStoreError, aprovar_curso, calibracao_dificuldade, calibracao_exercicios,
    calibracao_tutor, criar_curso, list_lessons_pendentes, registrar_tentativa_quiz,
    save_exercise, save_exercise_attempt, save_lesson_content, save_tutor_message,
)
from curso.curriculum_agent import manifest_from_roadmap


def _criar_curso_com_aula_dificuldade(user_key: str, dificuldade: int) -> tuple[str, str]:
    manifest = {
        "title": "Curso teste dificuldade", "description": "", "audience": "estudante",
        "difficulty": "avancado", "estimated_duration_min": 10, "style": "pratico",
        "learning_objectives": [], "prerequisites": [],
        "modules": [{"title": "M1", "objective": "", "lessons": [
            {"title": "L1", "objective": "", "duration_min": 10, "concepts": [],
             "dificuldade_estimada": dificuldade}
        ]}],
    }
    curso = criar_curso(user_key, "documento", manifest)
    course_id = curso["course_id"]
    aprovar_curso(course_id, user_key)
    lesson_id = list_lessons_pendentes(course_id)[0]["id"]
    save_lesson_content(lesson_id, explicacao="conteúdo de teste. " * 10, resumo="r", key_takeaways=[])
    return course_id, lesson_id


def _criar_curso_com_aula(user_key: str) -> tuple[str, str]:
    manifest = {
        "title": "Curso teste calibração", "description": "", "audience": "estudante",
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
    save_lesson_content(lesson_id, explicacao="conteúdo de teste. " * 10, resumo="r", key_takeaways=[])
    return course_id, lesson_id


class TestRegistrarTentativaQuiz:
    def test_acertos_maior_que_total_falha(self):
        with pytest.raises(CursoStoreError, match="acertos"):
            registrar_tentativa_quiz("qualquer-lesson-id", "aluno", total_perguntas=1, acertos=2)

    def test_total_perguntas_zero_falha(self):
        with pytest.raises(CursoStoreError):
            registrar_tentativa_quiz("qualquer-lesson-id", "aluno", total_perguntas=0, acertos=0)


class TestCalibracaoExercicios:
    def test_desalinhamento_nota_baixa_prevista_mas_aluno_vai_bem_depois(self):
        """O cenário central: ExerciseAgent previu nota baixa (20%), mas
        o aluno tirou 100% no quiz da mesma aula logo depois — isso
        precisa aparecer na faixa 'baixa' com media_real alta, provando
        o desalinhamento pra quem olhar o painel."""
        course_id, lesson_id = _criar_curso_com_aula("aluno_calib_1")
        ex_id = save_exercise(lesson_id, {"tipo": "problema", "enunciado": "e",
                                            "resposta_esperada": "r", "avaliacao_criteria": "c"})
        save_exercise_attempt(ex_id, "aluno_calib_1", "resposta fraca", {"nota_pct": 20, "feedback": "f"})
        time.sleep(0.02)
        registrar_tentativa_quiz(lesson_id, "aluno_calib_1", total_perguntas=1, acertos=1)

        resultado = calibracao_exercicios(course_id=course_id)
        assert len(resultado) == 1
        assert resultado[0]["faixa_prevista"] == "baixa (0-40)"
        assert float(resultado[0]["media_real"]) == 100.0

    def test_quiz_respondido_antes_do_exercicio_nao_conta(self):
        """Só conta 'resultado depois' — quiz respondido ANTES do
        exercício não prova nada sobre a nota que o exercício deu."""
        course_id, lesson_id = _criar_curso_com_aula("aluno_calib_2")
        registrar_tentativa_quiz(lesson_id, "aluno_calib_2", total_perguntas=1, acertos=1)
        time.sleep(0.02)
        ex_id = save_exercise(lesson_id, {"tipo": "problema", "enunciado": "e",
                                            "resposta_esperada": "r", "avaliacao_criteria": "c"})
        save_exercise_attempt(ex_id, "aluno_calib_2", "resposta", {"nota_pct": 50, "feedback": "f"})

        resultado = calibracao_exercicios(course_id=course_id)
        assert resultado == []

    def test_filtra_por_curso(self):
        course_id_a, lesson_id_a = _criar_curso_com_aula("aluno_calib_3a")
        course_id_b, _ = _criar_curso_com_aula("aluno_calib_3b")
        ex_id = save_exercise(lesson_id_a, {"tipo": "problema", "enunciado": "e",
                                              "resposta_esperada": "r", "avaliacao_criteria": "c"})
        save_exercise_attempt(ex_id, "aluno_calib_3a", "r", {"nota_pct": 80, "feedback": "f"})
        time.sleep(0.02)
        registrar_tentativa_quiz(lesson_id_a, "aluno_calib_3a", total_perguntas=1, acertos=1)

        assert len(calibracao_exercicios(course_id=course_id_a)) == 1
        assert calibracao_exercicios(course_id=course_id_b) == []


class TestCalibracaoTutor:
    def test_pergunta_unica_conta_como_resolvida(self):
        course_id, lesson_id = _criar_curso_com_aula("aluno_calib_4")
        save_tutor_message(lesson_id, "aluno_calib_4", "aluno", "pergunta única, nunca mais voltou")

        resultado = calibracao_tutor(course_id=course_id, janela_minutos=20)
        assert resultado["total_perguntas"] == 1
        assert resultado["resolvidas_sem_nova_pergunta"] == 1
        assert resultado["taxa_resolucao_pct"] == 100.0

    def test_pergunta_seguida_de_nova_pergunta_nao_conta_como_resolvida(self):
        course_id, lesson_id = _criar_curso_com_aula("aluno_calib_5")
        save_tutor_message(lesson_id, "aluno_calib_5", "aluno", "primeira pergunta")
        save_tutor_message(lesson_id, "aluno_calib_5", "tutor", "resposta")
        save_tutor_message(lesson_id, "aluno_calib_5", "aluno", "ainda não entendi")

        resultado = calibracao_tutor(course_id=course_id, janela_minutos=20)
        assert resultado["total_perguntas"] == 2
        assert resultado["resolvidas_sem_nova_pergunta"] == 1  # só a última pergunta da thread

    def test_sem_nenhuma_pergunta_nao_quebra(self):
        course_id, _ = _criar_curso_com_aula("aluno_calib_6")
        resultado = calibracao_tutor(course_id=course_id)
        assert resultado["total_perguntas"] == 0
        assert resultado["taxa_resolucao_pct"] is None


class TestCalibracaoDificuldade:
    def test_desalinhamento_dificuldade_alta_prevista_mas_acerto_real_alto(self):
        course_id, lesson_id = _criar_curso_com_aula_dificuldade("aluno_dif_1", dificuldade=85)
        registrar_tentativa_quiz(lesson_id, "aluno_dif_1", total_perguntas=1, acertos=1)

        resultado = calibracao_dificuldade(course_id=course_id)
        assert len(resultado) == 1
        assert resultado[0]["faixa_prevista"] == "alta (70-100)"
        assert float(resultado[0]["media_acerto_real"]) == 100.0

    def test_aula_sem_quiz_respondido_nao_quebra(self):
        course_id, _ = _criar_curso_com_aula_dificuldade("aluno_dif_2", dificuldade=20)
        resultado = calibracao_dificuldade(course_id=course_id)
        assert resultado[0]["n_tentativas_quiz"] == 0
        assert resultado[0]["media_acerto_real"] is None

    def test_filtra_por_curso(self):
        course_id_a, _ = _criar_curso_com_aula_dificuldade("aluno_dif_3a", dificuldade=60)
        course_id_b, _ = _criar_curso_com_aula_dificuldade("aluno_dif_3b", dificuldade=60)
        assert calibracao_dificuldade(course_id=course_id_a)[0]["n_aulas"] == 1
        assert calibracao_dificuldade(course_id=course_id_b)[0]["n_aulas"] == 1


class TestManifestFromRoadmapDerivaDificuldade:
    def test_nivel_avancado_vira_dificuldade_alta(self):
        roadmap = {"nivel": "avançado", "resumo": "r", "modulos": [
            {"titulo": "M1", "objetivo": "o", "duracao_estimada": "10 min", "topicos": []}
        ]}
        manifest = manifest_from_roadmap(roadmap, "Tópico")
        assert manifest["modules"][0]["lessons"][0]["dificuldade_estimada"] == 80

    def test_nivel_iniciante_vira_dificuldade_baixa(self):
        roadmap = {"nivel": "iniciante", "resumo": "r", "modulos": [
            {"titulo": "M1", "objetivo": "o", "duracao_estimada": "10 min", "topicos": []}
        ]}
        manifest = manifest_from_roadmap(roadmap, "Tópico")
        assert manifest["modules"][0]["lessons"][0]["dificuldade_estimada"] == 30

    def test_nivel_desconhecido_usa_default(self):
        roadmap = {"nivel": "", "resumo": "r", "modulos": [
            {"titulo": "M1", "objetivo": "o", "duracao_estimada": "10 min", "topicos": []}
        ]}
        manifest = manifest_from_roadmap(roadmap, "Tópico")
        assert manifest["modules"][0]["lessons"][0]["dificuldade_estimada"] == 50
