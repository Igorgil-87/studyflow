"""tests/test_anti_slop.py — testa tools/anti_slop.py."""

import importlib.util
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_anti_slop():
    """Importa direto do arquivo, contornando tools/__init__.py — esse
    __init__ carrega o pacote tools/ inteiro (Whisper, yt-dlp, moviepy...)
    só por causa de outros módulos vizinhos, o que forçaria instalar
    dependências pesadas só pra testar uma string. anti_slop.py não
    depende de nada disso."""
    spec = importlib.util.spec_from_file_location(
        "anti_slop", _PROJECT_ROOT / "tools" / "anti_slop.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_anti_slop_rules_nao_esta_vazio():
    mod = _load_anti_slop()
    assert len(mod.ANTI_SLOP_RULES) > 100


def test_anti_slop_rules_sem_chaves():
    """Regressão: o texto é injetado dentro de um ChatPromptTemplate do
    LangChain (highlight_extractor.py), que usa {chave} pra variáveis de
    template. Se esse texto tiver uma chave literal, quebra o template
    inteiro na hora de formatar o prompt."""
    mod = _load_anti_slop()
    assert "{" not in mod.ANTI_SLOP_RULES
    assert "}" not in mod.ANTI_SLOP_RULES
