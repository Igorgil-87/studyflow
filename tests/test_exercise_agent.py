"""tests/test_exercise_agent.py — cobre curso/exercise_agent.py com LLM mockado."""

from unittest.mock import patch

import pytest

from curso.exercise_agent import (
    AvaliacaoDraft, ExercicioDraft, ExerciseAgentError, avaliar_resposta, gerar_exercicio,
)


def test_gerar_exercicio_conteudo_curto_falha_sem_chamar_llm():
    with pytest.raises(ExerciseAgentError, match="insuficiente"):
        gerar_exercicio("Aula", "curto")


def test_gerar_exercicio():
    fake_ex = ExercicioDraft(
        tipo="estudo_de_caso", enunciado="Implemente RAG pra 2M documentos.",
        resposta_esperada="chunking, embeddings, vector db",
        avaliacao_criteria="cobre os 3 pontos principais",
    )

    class FakeChain:
        def invoke(self, args):
            return fake_ex

    with patch("curso.exercise_agent._build_chain_gerar", return_value=FakeChain()):
        ex = gerar_exercicio("RAG", "Explicação completa sobre RAG. " * 10)

    assert ex["tipo"] == "estudo_de_caso"
    assert "2M documentos" in ex["enunciado"]


def test_avaliar_resposta_vazia_falha():
    with pytest.raises(ExerciseAgentError, match="vazia"):
        avaliar_resposta("explicação", "enunciado", "critério", "   ")


def test_avaliar_resposta():
    fake_aval = AvaliacaoDraft(
        nota_pct=75, feedback="Bom, mas faltou mencionar vector db",
        pontos_fortes=["citou chunking"], pontos_a_melhorar=["faltou vector db"],
    )

    class FakeChain:
        def invoke(self, args):
            return fake_aval

    with patch("curso.exercise_agent._build_chain_avaliar", return_value=FakeChain()):
        aval = avaliar_resposta("explicação da aula", "enunciado", "critério", "Eu usaria chunking.")

    assert aval["nota_pct"] == 75
    assert aval["pontos_fortes"] == ["citou chunking"]


def test_gerar_exercicio_falha_dos_dois_provedores():
    class FailingChain:
        def invoke(self, args):
            raise RuntimeError("boom")

    with patch("curso.exercise_agent._build_chain_gerar", return_value=FailingChain()):
        with pytest.raises(ExerciseAgentError):
            gerar_exercicio("Aula", "Explicação completa. " * 10)
