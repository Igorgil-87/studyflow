"""tests/test_llm_fallback.py — testa tools/llm_fallback.py: o
fallback real entre Anthropic e OpenAI quando um provedor falha."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tools.llm_fallback as fb  # noqa: E402


def test_anthropic_ok_nunca_chama_openai():
    os.environ["ANTHROPIC_API_KEY"] = "fake"
    os.environ["OPENAI_API_KEY"] = "fake"
    with patch.object(fb, "_call_anthropic", return_value="resposta da anthropic"), \
         patch.object(fb, "_call_openai") as m_openai:
        resultado = fb.call_with_fallback("sistema", "usuario")
    assert resultado == "resposta da anthropic"
    m_openai.assert_not_called()


def test_anthropic_falha_openai_assume():
    os.environ["ANTHROPIC_API_KEY"] = "fake"
    os.environ["OPENAI_API_KEY"] = "fake"
    with patch.object(fb, "_call_anthropic", side_effect=RuntimeError("fora do ar")), \
         patch.object(fb, "_call_openai", return_value="resposta da openai") as m_openai:
        resultado = fb.call_with_fallback("sistema", "usuario")
    assert resultado == "resposta da openai"
    m_openai.assert_called_once()


def test_os_dois_falham_propaga_erro_com_os_dois_motivos():
    os.environ["ANTHROPIC_API_KEY"] = "fake"
    os.environ["OPENAI_API_KEY"] = "fake"
    with patch.object(fb, "_call_anthropic", side_effect=RuntimeError("motivo anthropic")), \
         patch.object(fb, "_call_openai", side_effect=RuntimeError("motivo openai")):
        try:
            fb.call_with_fallback("sistema", "usuario")
            assert False, "deveria ter levantado LLMFallbackError"
        except fb.LLMFallbackError as e:
            assert "motivo anthropic" in str(e)
            assert "motivo openai" in str(e)


def test_sem_chave_anthropic_pula_direto_pra_openai():
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ["OPENAI_API_KEY"] = "fake"
    with patch.object(fb, "_call_anthropic") as m_anthropic, \
         patch.object(fb, "_call_openai", return_value="openai direto") as m_openai:
        resultado = fb.call_with_fallback("sistema", "usuario")
    assert resultado == "openai direto"
    m_anthropic.assert_not_called()
    m_openai.assert_called_once()
    os.environ["ANTHROPIC_API_KEY"] = "fake"  # restaura pros próximos testes


def test_build_llm_with_fallback_tenta_principal_depois_cai_pro_alternativo():
    """Versão LangChain (.with_fallbacks()) — usada em código que monta
    chain (prompt | llm | parser), diferente do SDK cru testado acima."""
    os.environ["OPENAI_API_KEY"] = "fake"
    os.environ["ANTHROPIC_API_KEY"] = "fake"
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import AIMessage

    chamadas = []

    def fake_openai_invoke(self, *a, **k):
        chamadas.append("openai")
        raise RuntimeError("OpenAI fora do ar (simulado)")

    def fake_anthropic_invoke(self, *a, **k):
        chamadas.append("anthropic")
        return AIMessage(content="resposta do fallback")

    llm = fb.build_llm_with_fallback(primary_provider="openai", primary_model="gpt-4o-mini")
    with patch.object(ChatOpenAI, "invoke", fake_openai_invoke), \
         patch.object(ChatAnthropic, "invoke", fake_anthropic_invoke):
        resultado = llm.invoke("teste")

    assert chamadas == ["openai", "anthropic"]
    assert resultado.content == "resposta do fallback"
