"""tests/test_yt_error_classifier.py — testa tools/yt_error_classifier.py.
Inclui o erro EXATO que apareceu em produção (vídeo privado), pra nunca
regredir de volta pra mensagem genérica errada nesse caso."""

import importlib.util
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "yt_error_classifier", _PROJECT_ROOT / "tools" / "yt_error_classifier.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()
classify_download_error = _mod.classify_download_error


def test_video_privado_erro_real_reportado_pelo_usuario():
    """Erro EXATO reportado em produção — vídeo WK7tr-eFAXY."""
    erro = ("ERROR: [youtube] WK7tr-eFAXY: Private video. Sign in if "
            "you've been granted access to this video. Use "
            "--cookies-from-browser or --cookies for the authentication.")
    msg = classify_download_error(erro)
    assert "PRIVADO" in msg
    assert "Atualizar o yt-dlp não resolve" in msg


def test_bloqueio_de_bot_sugere_atualizar_e_cookies():
    erro = "ERROR: [youtube] abc: Sign in to confirm you're not a bot."
    msg = classify_download_error(erro)
    assert "bot" in msg
    assert "Atualize o yt-dlp" in msg


def test_restricao_de_idade():
    erro = "ERROR: [youtube] xyz: Sign in to confirm your age."
    msg = classify_download_error(erro)
    assert "restrição de idade" in msg


def test_video_removido_ou_indisponivel():
    erro = "ERROR: [youtube] def: Video unavailable."
    msg = classify_download_error(erro)
    assert "removido" in msg or "indisponível" in msg


def test_erro_desconhecido_nao_finge_certeza():
    erro = "ERROR: some random network thing nobody has seen before"
    msg = classify_download_error(erro)
    assert "Pode ser" in msg


def test_sempre_inclui_o_detalhe_original():
    """Não importa a classificação, o erro cru original sempre precisa
    aparecer no final — pra debug, mesmo quando a classificação erra."""
    erro = "ERROR: qualquer coisa aqui 12345"
    msg = classify_download_error(erro)
    assert erro in msg
