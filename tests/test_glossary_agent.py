"""tests/test_glossary_agent.py — cobre curso/glossary_agent.py com LLM mockado."""

from unittest.mock import patch

import pytest

from curso.glossary_agent import (
    GlossarioDraft, GlossaryAgentError, TermoGlossario, gerar_glossario,
)


def test_lista_vazia_nao_chama_llm():
    with patch("curso.glossary_agent._build_chain") as mock_build:
        assert gerar_glossario("Curso X", "desc", []) == {}
    mock_build.assert_not_called()


def test_gera_definicoes():
    fake_draft = GlossarioDraft(termos=[
        TermoGlossario(termo="embedding", definicao="representação vetorial de um dado"),
        TermoGlossario(termo="vetor", definicao="lista ordenada de números"),
    ])

    class FakeChain:
        def invoke(self, args):
            return fake_draft

    with patch("curso.glossary_agent._build_chain", return_value=FakeChain()):
        resultado = gerar_glossario("RAG do Zero", "curso sobre RAG", ["embedding", "vetor"])

    assert resultado == {
        "embedding": "representação vetorial de um dado",
        "vetor": "lista ordenada de números",
    }


def test_falha_dos_dois_provedores_vira_glossary_agent_error():
    class FailingChain:
        def invoke(self, args):
            raise RuntimeError("boom")

    with patch("curso.glossary_agent._build_chain", return_value=FailingChain()):
        with pytest.raises(GlossaryAgentError):
            gerar_glossario("Curso", "desc", ["a"])
