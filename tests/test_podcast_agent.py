"""tests/test_podcast_agent.py — cobre curso/podcast_agent.py com LLM mockado."""

from unittest.mock import patch

import pytest

from curso.podcast_agent import Fala, PodcastAgentError, PodcastScript, gerar_podcast_script


def test_conteudo_curto_demais_falha_sem_chamar_llm():
    with pytest.raises(PodcastAgentError, match="insuficiente"):
        gerar_podcast_script("Aula", "curto", ["a"])


def test_gera_roteiro():
    fake_draft = PodcastScript(turns=[
        Fala(speaker="A", text="Vamos falar de embeddings hoje."),
        Fala(speaker="B", text="Ótimo tema! Embedding é uma representação vetorial."),
        Fala(speaker="A", text="E pra que serve isso na prática?"),
        Fala(speaker="B", text="Serve pra buscar por significado, não só por palavra exata."),
        Fala(speaker="A", text="Faz sentido."),
        Fala(speaker="B", text="Exatamente, é a base de todo sistema de busca semântica."),
    ])

    class FakeChain:
        def invoke(self, args):
            return fake_draft

    with patch("curso.podcast_agent._build_chain", return_value=FakeChain()):
        script = gerar_podcast_script("Embeddings", "Explicação completa. " * 10, ["embedding"])

    assert len(script["turns"]) == 6
    assert script["turns"][0]["speaker"] == "A"


def test_speaker_invalido_vira_erro_claro():
    fake_draft = PodcastScript(turns=[
        Fala(speaker="A", text="ok"), Fala(speaker="C", text="inválido"),
        Fala(speaker="B", text="ok"), Fala(speaker="A", text="ok"),
        Fala(speaker="B", text="ok"), Fala(speaker="A", text="ok"),
    ])

    class FakeChain:
        def invoke(self, args):
            return fake_draft

    with patch("curso.podcast_agent._build_chain", return_value=FakeChain()):
        with pytest.raises(PodcastAgentError, match="speaker inválido"):
            gerar_podcast_script("Aula", "Explicação completa. " * 10, ["c1"])


def test_falha_dos_dois_provedores_vira_podcast_agent_error():
    class FailingChain:
        def invoke(self, args):
            raise RuntimeError("boom")

    with patch("curso.podcast_agent._build_chain", return_value=FailingChain()):
        with pytest.raises(PodcastAgentError):
            gerar_podcast_script("Aula", "Explicação completa. " * 10, ["c1"])
