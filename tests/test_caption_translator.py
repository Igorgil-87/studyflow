"""tests/test_caption_translator.py — testa tools/caption_translator.py.
Mocka a chamada da Anthropic (não precisa de API key de verdade). Cobre
especificamente o cenário que apareceu em produção: a IA devolve menos
blocos do que devia (contagem não bate) — antes descartava a tradução
inteira, agora tenta de novo e preenche só o que faltar com o original."""

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_module_with_fake_anthropic(respostas: list[str]):
    """Carrega tools/caption_translator.py com um cliente Anthropic falso
    que devolve uma resposta DIFERENTE a cada chamada (na ordem de
    `respostas`) — necessário pra simular retry (1ª tentativa incompleta,
    2ª tentativa completa o que faltou)."""
    # importa o pacote tools ANTES de mockar o anthropic — caption_translator
    # agora importa tools.llm_fallback, e isso dispara tools/__init__.py,
    # que carrega outras classes que usam o anthropic de verdade.
    import tools.llm_fallback  # noqa: F401

    fake_anthropic = types.ModuleType("anthropic")
    fila = list(respostas)

    class FakeAPIError(Exception):
        pass

    class FakeMessages:
        def create(self, **kwargs):
            texto = fila.pop(0) if fila else respostas[-1]
            resp = MagicMock()
            block = MagicMock()
            block.type = "text"
            block.text = texto
            resp.content = [block]
            return resp

    class FakeAnthropic:
        def __init__(self, *a, **k):
            self.messages = FakeMessages()

    fake_anthropic.Anthropic = FakeAnthropic
    fake_anthropic.APIError = FakeAPIError
    sys.modules["anthropic"] = fake_anthropic

    import os
    os.environ["ANTHROPIC_API_KEY"] = "fake-key-para-teste"

    spec = importlib.util.spec_from_file_location(
        "caption_translator", _PROJECT_ROOT / "tools" / "caption_translator.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_traduz_preservando_ordem_e_quantidade():
    resposta = json.dumps([{"i": 0, "t": "Olá"}, {"i": 1, "t": "mundo"}, {"i": 2, "t": "bom dia"}])
    mod = _load_module_with_fake_anthropic([resposta])
    resultado = mod.translate_caption_texts(["hello", "world", "good morning"], "pt")
    assert resultado == ["Olá", "mundo", "bom dia"]


def test_aceita_resposta_com_markdown_fence():
    resposta = "```json\n" + json.dumps([{"i": 0, "t": "Olá"}, {"i": 1, "t": "mundo"}]) + "\n```"
    mod = _load_module_with_fake_anthropic([resposta])
    resultado = mod.translate_caption_texts(["hello", "world"], "pt")
    assert resultado == ["Olá", "mundo"]


def test_bloco_faltando_e_recuperado_no_retry():
    """O cenário EXATO que apareceu em produção: 60 enviados, 59 vieram
    na 1ª tentativa (índice 2 faltando). Antes: descartava tudo. Agora:
    tenta de novo só o que faltou, e recupera."""
    primeira = json.dumps([{"i": 0, "t": "Olá"}, {"i": 1, "t": "mundo"}])  # falta o índice 2
    segunda = json.dumps([{"i": 2, "t": "bom dia"}])  # retry só do que faltou
    mod = _load_module_with_fake_anthropic([primeira, segunda])
    resultado = mod.translate_caption_texts(["hello", "world", "good morning"], "pt")
    assert resultado == ["Olá", "mundo", "bom dia"]


def test_bloco_ainda_faltando_apos_retry_usa_original():
    """Se depois de 2 tentativas ainda faltar um bloco, usa o texto
    ORIGINAL só pra esse — não descarta a tradução inteira por causa de 1."""
    primeira = json.dumps([{"i": 0, "t": "Olá"}])  # faltam 1 e 2
    segunda = json.dumps([{"i": 1, "t": "mundo"}])  # retry recupera só o 1, ainda falta o 2
    mod = _load_module_with_fake_anthropic([primeira, segunda])
    resultado = mod.translate_caption_texts(["hello", "world", "good morning"], "pt")
    assert resultado == ["Olá", "mundo", "good morning"]  # índice 2 ficou no original


def test_falha_total_de_api_nas_duas_tentativas_propaga_erro():
    """Só propaga erro de verdade quando as DUAS tentativas falham por
    completo (erro de API/parsing) — não por causa só de contagem."""
    mod = _load_module_with_fake_anthropic(["isso não é json válido", "isso também não é"])
    try:
        mod.translate_caption_texts(["hello", "world"], "pt")
        assert False, "deveria ter levantado CaptionTranslationError"
    except mod.CaptionTranslationError:
        pass


def test_lista_vazia_nao_chama_api():
    mod = _load_module_with_fake_anthropic(["não deveria nem ser lido"])
    resultado = mod.translate_caption_texts([], "pt")
    assert resultado == []
