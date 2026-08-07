"""tests/test_growth_analyzer.py — testa tools/growth_analyzer.py.
Mocka a chamada da Anthropic (não precisa de API key de verdade)."""

import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_module_with_fake_anthropic(fake_response_text: str):
    # importa o pacote tools ANTES de mockar o anthropic — o
    # growth_analyzer agora importa tools.clip_rules (TIPOS_GANCHO
    # compartilhado), e isso dispara tools/__init__.py, que carrega
    # outras classes que usam o anthropic de verdade. Importando tudo
    # isso primeiro, o mock abaixo não contamina esses outros módulos.
    import tools.clip_rules  # noqa: F401

    fake_anthropic = types.ModuleType("anthropic")

    class FakeAPIError(Exception):
        pass

    class FakeMessages:
        def create(self, **kwargs):
            resp = MagicMock()
            block = MagicMock()
            block.type = "text"
            block.text = fake_response_text
            resp.content = [block]
            return resp

    class FakeAnthropic:
        def __init__(self, *a, **k):
            self.messages = FakeMessages()

    fake_anthropic.Anthropic = FakeAnthropic
    fake_anthropic.APIError = FakeAPIError
    sys.modules["anthropic"] = fake_anthropic
    os.environ["ANTHROPIC_API_KEY"] = "fake-key-para-teste"

    spec = importlib.util.spec_from_file_location(
        "growth_analyzer", _PROJECT_ROOT / "analytics" / "growth_analyzer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_analisa_post_com_gancho_valido():
    resposta = json.dumps({
        "tipo_gancho": "choque", "criterios_virais": {"relatable": True},
        "taticas_engajamento": [], "tem_cta_claro": False, "resumo": "teste",
    })
    mod = _load_module_with_fake_anthropic(resposta)
    analise = mod.analisar_publicacao("legenda de teste", None, 1000, 50)
    assert analise["tipo_gancho"] == "choque"


def test_tipo_gancho_invalido_vira_nenhum_claro():
    resposta = json.dumps({
        "tipo_gancho": "tipo_que_nao_existe", "criterios_virais": {},
        "taticas_engajamento": [], "tem_cta_claro": False, "resumo": "teste",
    })
    mod = _load_module_with_fake_anthropic(resposta)
    analise = mod.analisar_publicacao("legenda", None, 100, 5)
    assert analise["tipo_gancho"] == "nenhum_claro"


def test_rejeita_post_sem_conteudo():
    mod = _load_module_with_fake_anthropic('{"tipo_gancho": "choque"}')
    try:
        mod.analisar_publicacao("", None, 100, 5)
        assert False, "deveria ter rejeitado"
    except mod.GrowthAnalyzerError:
        pass


def test_todos_tipos_gancho_da_lista_sao_aceitos():
    mod = _load_module_with_fake_anthropic("{}")
    for tipo in mod.TIPOS_GANCHO:
        assert isinstance(tipo, str) and tipo
