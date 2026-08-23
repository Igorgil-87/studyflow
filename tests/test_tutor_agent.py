"""tests/test_tutor_agent.py — cobre curso/tutor_agent.py com LLM mockado."""

from unittest.mock import MagicMock, patch

import pytest

from curso.tutor_agent import TutorAgentError, perguntar


def test_pergunta_vazia_falha_sem_chamar_llm():
    with pytest.raises(TutorAgentError, match="vazia"):
        perguntar("", "Aula", "explicação", [], [])


def test_aula_sem_conteudo_falha():
    with pytest.raises(TutorAgentError, match="não tem conteúdo"):
        perguntar("oi", "Aula", "", [], [])


def test_responde_usando_historico_e_rag():
    mensagens_capturadas = []

    class FakeLLM:
        def invoke(self, mensagens):
            mensagens_capturadas.extend(mensagens)
            resp = MagicMock()
            resp.content = "Embedding é uma representação vetorial, sim."
            return resp

    with patch("curso.tutor_agent._montar_llm", return_value=FakeLLM()):
        resposta = perguntar(
            "Pode confirmar isso?", "Embeddings", "Embeddings são vetores. " * 5,
            [{"text": "trecho do documento sobre embeddings"}],
            [{"role": "aluno", "content": "O que é embedding?"},
             {"role": "tutor", "content": "É um vetor."}],
        )

    assert resposta == "Embedding é uma representação vetorial, sim."
    # system + 2 turnos de histórico + pergunta atual
    assert len(mensagens_capturadas) == 4
    assert "trecho do documento" in mensagens_capturadas[0].content


def test_historico_e_truncado_no_maximo(monkeypatch):
    monkeypatch.setattr("curso.tutor_agent.MAX_HISTORICO_TURNOS", 2)
    mensagens_capturadas = []

    class FakeLLM:
        def invoke(self, mensagens):
            mensagens_capturadas.extend(mensagens)
            resp = MagicMock()
            resp.content = "ok"
            return resp

    historico_longo = [{"role": "aluno" if i % 2 == 0 else "tutor", "content": f"msg{i}"}
                        for i in range(10)]
    with patch("curso.tutor_agent._montar_llm", return_value=FakeLLM()):
        perguntar("nova pergunta", "Aula", "Explicação suficientemente longa. " * 5,
                   [], historico_longo)

    # system + 2 (truncado) + pergunta atual
    assert len(mensagens_capturadas) == 4


def test_falha_dos_dois_provedores_vira_tutor_agent_error():
    class FailingLLM:
        def invoke(self, mensagens):
            raise RuntimeError("boom")

    with patch("curso.tutor_agent._montar_llm", return_value=FailingLLM()):
        with pytest.raises(TutorAgentError):
            perguntar("pergunta", "Aula", "Explicação longa o bastante. " * 5, [], [])
