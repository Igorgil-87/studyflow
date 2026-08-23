"""tests/test_storyboard_agent.py — cobre curso/storyboard_agent.py com
LLM mockado (não gasta token real)."""

from unittest.mock import patch

import pytest

from curso.storyboard_agent import (
    Cena, StoryboardAgentError, StoryboardDraft, gerar_storyboard,
)


def test_conteudo_curto_demais_falha_sem_chamar_llm():
    with pytest.raises(StoryboardAgentError, match="insuficiente"):
        gerar_storyboard("Aula", "curto", ["a"])


def test_gera_storyboard():
    fake_draft = StoryboardDraft(scenes=[
        Cena(tipo="diagrama", narration="Embeddings são vetores.",
             visual_description="Embeddings\n- vetor", duration_seconds=5,
             source_reference="takeaway 1"),
        Cena(tipo="diagrama", narration="Vetores capturam significado.",
             visual_description="Significado\n- semântico", duration_seconds=4,
             source_reference="takeaway 2"),
    ])

    class FakeChain:
        def invoke(self, args):
            return fake_draft

    with patch("curso.storyboard_agent._build_chain", return_value=FakeChain()):
        storyboard = gerar_storyboard(
            "Embeddings", "Explicação completa sobre embeddings. " * 10, ["embedding", "vetor"]
        )

    assert len(storyboard["scenes"]) == 2
    assert storyboard["scenes"][0]["tipo"] == "diagrama"
    assert storyboard["scenes"][0]["source_reference"] == "takeaway 1"


def test_falha_dos_dois_provedores_vira_storyboard_agent_error():
    class FailingChain:
        def invoke(self, args):
            raise RuntimeError("boom")

    with patch("curso.storyboard_agent._build_chain", return_value=FailingChain()):
        with pytest.raises(StoryboardAgentError):
            gerar_storyboard("Aula", "Explicação suficientemente longa. " * 10, ["c1"])
