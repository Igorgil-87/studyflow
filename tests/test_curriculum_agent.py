"""tests/test_curriculum_agent.py — cobre curso/curriculum_agent.py com
LLM mockado (não gasta token real)."""

from unittest.mock import patch

import pytest

from curso.curriculum_agent import (
    CourseManifestDraft, CurriculumAgentError, KnowledgeGap, LessonSpec,
    ModuleSpec, gerar_manifesto, manifest_from_roadmap,
)


def _fake_draft():
    return CourseManifestDraft(
        title="RAG do Zero", description="curso gerado a partir do PDF",
        audience="estudante", difficulty="fundamentos", estimated_duration_min=45,
        style="pratico", learning_objectives=["entender RAG"], prerequisites=[],
        modules=[ModuleSpec(
            title="Fundamentos", objective="entender embeddings",
            lessons=[LessonSpec(title="Embeddings", objective="explicar",
                                 duration_min=15, concepts=["embedding"])],
        )],
        knowledge_gaps=[KnowledgeGap(descricao="falta vector db", conceito_faltante="vector database")],
    )


class _FakeChain:
    def invoke(self, args):
        return _fake_draft()


def test_material_curto_demais_falha_sem_chamar_llm():
    with pytest.raises(CurriculumAgentError, match="insuficiente"):
        gerar_manifesto("oi")


def test_gera_manifesto_normaliza_valores_invalidos():
    with patch("curso.curriculum_agent._build_chain", return_value=_FakeChain()):
        manifest = gerar_manifesto(
            "texto de material " * 30, publico="INVALIDO", nivel="???", estilo="???"
        )
    assert manifest["title"] == "RAG do Zero"
    assert manifest["status"] == "aguardando_aprovacao"
    assert manifest["audience"] == "estudante"      # fallback pro default válido
    assert manifest["difficulty"] == "fundamentos"  # idem
    assert len(manifest["modules"]) == 1
    assert manifest["knowledge_gaps"][0]["conceito_faltante"] == "vector database"


def test_falha_dos_dois_provedores_vira_curriculum_agent_error():
    class FailingChain:
        def invoke(self, args):
            raise RuntimeError("Anthropic e OpenAI indisponíveis")

    with patch("curso.curriculum_agent._build_chain", return_value=FailingChain()):
        with pytest.raises(CurriculumAgentError):
            gerar_manifesto("texto de material " * 30)


def test_manifest_from_roadmap_soma_duracao_e_mapeia_nivel():
    roadmap = {
        "tema": "RAG", "nivel": "intermediário", "resumo": "aprenda RAG do zero",
        "pre_requisitos": ["python básico"],
        "modulos": [
            {"titulo": "Fundamentos", "objetivo": "entender embeddings",
             "topicos": ["embedding", "vetor"], "duracao_estimada": "30 min"},
            {"titulo": "Avançado", "objetivo": "implementar",
             "topicos": ["chunking"], "duracao_estimada": "1h"},
        ],
    }
    manifest = manifest_from_roadmap(roadmap, "Como funciona RAG")

    assert manifest["title"] == "Como funciona RAG"
    assert manifest["difficulty"] == "intermediario"
    assert manifest["estimated_duration_min"] == 90  # 30 + 60
    assert len(manifest["modules"]) == 2
    assert manifest["status"] == "aguardando_aprovacao"


def test_manifest_from_roadmap_nao_chama_llm():
    """Reaproveitar o roadmap da Opção 1 não pode custar token extra."""
    with patch("curso.curriculum_agent._build_chain") as mock_build:
        manifest_from_roadmap({"modulos": []}, "Tema qualquer")
        mock_build.assert_not_called()
