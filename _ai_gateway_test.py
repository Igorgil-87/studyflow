import os
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-openai")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic")
os.environ.pop("GEMINI_API_KEY", None)

from ai_gateway import gateway as g


def test_status_nunca_expoe_secret():
    rows = g.provider_status()
    payload = repr(rows)
    assert "test-openai" not in payload
    assert "test-anthropic" not in payload
    assert any(r["provider"] == "gemini" and not r["configured"] for r in rows)


def test_fallback_gemini_sem_chave_vai_openai():
    with patch.object(g, "_call_openai", return_value="ok-openai") as openai_call:
        result = g.generate_text(
            "teste", preferred_provider="gemini", fallback_providers=["openai", "anthropic"],
            operation="gateway_test", trace_id="gw-test-1",
        )
    assert result.text == "ok-openai"
    assert result.provider == "openai"
    assert openai_call.called


def test_provider_isolado_nao_faz_fallback():
    with patch.object(g, "_call_openai", side_effect=RuntimeError("openai down")), \
         patch.object(g, "_call_anthropic", return_value="nao deveria chamar") as anth:
        try:
            g.generate_text("x", preferred_provider="openai", fallback_providers=[])
        except g.AIGatewayError:
            pass
        else:
            raise AssertionError("esperava AIGatewayError")
    assert not anth.called


def test_gemini_configurado_pode_ser_primario():
    os.environ["GEMINI_API_KEY"] = "test-gemini"
    try:
        with patch.object(g, "_call_gemini", return_value="ok-gemini"):
            result = g.generate_text("x", preferred_provider="gemini", fallback_providers=[])
        assert result.provider == "gemini"
        assert result.text == "ok-gemini"
    finally:
        os.environ.pop("GEMINI_API_KEY", None)


if __name__ == "__main__":
    for fn in [test_status_nunca_expoe_secret, test_fallback_gemini_sem_chave_vai_openai,
               test_provider_isolado_nao_faz_fallback, test_gemini_configurado_pode_ser_primario]:
        fn()
    print("AI GATEWAY + FALLBACK + SECRET SAFETY OK ✅")
