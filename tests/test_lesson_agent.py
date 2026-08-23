"""tests/test_lesson_agent.py — cobre curso/lesson_agent.py com LLM
mockado (não gasta token real)."""

from unittest.mock import patch

import pytest
from langchain_core.runnables import RunnableLambda

from curso.lesson_agent import (
    LessonAgentError, LessonContentDraft, gerar_conteudo_aula, gerar_quiz_aula,
)


def test_material_curto_demais_falha_sem_chamar_llm():
    with pytest.raises(LessonAgentError, match="insuficiente"):
        gerar_conteudo_aula("Aula 1", "obj", ["c1"], "curto")


def test_gera_conteudo_aula():
    fake_draft = LessonContentDraft(
        explicacao="texto didático completo aqui",
        resumo="resumo curto",
        key_takeaways=["embedding", "vetor", "similaridade"],
    )

    class FakeChain:
        def invoke(self, args):
            return fake_draft

    with patch("curso.lesson_agent._build_chain", return_value=FakeChain()):
        conteudo = gerar_conteudo_aula(
            "Embeddings", "explicar embeddings", ["embedding", "vetor"],
            "material de referência " * 20,
        )
    assert conteudo["explicacao"] == "texto didático completo aqui"
    assert len(conteudo["key_takeaways"]) == 3


def test_falha_dos_dois_provedores_vira_lesson_agent_error():
    class FailingChain:
        def invoke(self, args):
            raise RuntimeError("Anthropic e OpenAI indisponíveis")

    with patch("curso.lesson_agent._build_chain", return_value=FailingChain()):
        with pytest.raises(LessonAgentError):
            gerar_conteudo_aula("Aula", "obj", ["c1"], "material " * 20)


def test_gerar_quiz_aula_usa_provider_anthropic(tmp_path):
    fake_json = (
        '{"tema": "Embeddings", "flashcards": '
        '[{"frente": "O que é embedding?", "verso": "resposta"}], "questoes": []}'
    )
    captured = {}

    def fake_build(temperature, primary_provider, primary_model, fallback_provider="anthropic", fallback_model=None):
        captured["primary_provider"] = primary_provider
        captured["fallback_provider"] = fallback_provider
        return RunnableLambda(lambda p: fake_json)

    with patch("tools.llm_fallback.build_llm_with_fallback", side_effect=fake_build):
        quiz = gerar_quiz_aula("Embeddings", "explicação da aula " * 10, num_flashcards=1, num_questions=0)

    assert captured["primary_provider"] == "anthropic"
    assert captured["fallback_provider"] == "openai"  # cruzado, não o mesmo provedor
    assert quiz["flashcards"][0]["frente"] == "O que é embedding?"


def test_gerar_quiz_aula_propaga_erro_como_lesson_agent_error():
    def fake_build(*a, **k):
        return RunnableLambda(lambda p: (_ for _ in ()).throw(RuntimeError("boom")))

    with patch("tools.llm_fallback.build_llm_with_fallback", side_effect=fake_build):
        with pytest.raises(LessonAgentError):
            gerar_quiz_aula("Aula", "explicação " * 10)
