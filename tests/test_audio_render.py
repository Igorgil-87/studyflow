"""tests/test_audio_render.py — cobre curso/audio_render.py e
curso/tts.py.concatenar_audios. ffmpeg roda DE VERDADE; só a chamada de
rede pro TTS (edge-tts) é mockada, substituída por tom sintético gerado
com ffmpeg — mesma estratégia de tests/test_video_render.py.
"""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="ffmpeg/ffprobe não disponíveis neste ambiente",
)

from curso.audio_render import (  # noqa: E402
    AudioRenderError, gerar_audio_aula, gerar_podcast_aula,
)
from curso.tts import medir_duracao_audio  # noqa: E402


def _fake_narrar(texto, out_path, voice="pt-BR-AntonioNeural", duracao=1.5):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={duracao}",
         "-ar", "24000", out_path],
        capture_output=True, check=True,
    )
    return out_path


def test_gerar_audio_aula_texto_vazio_falha_sem_chamar_tts(tmp_path):
    with pytest.raises(AudioRenderError, match="curto demais"):
        gerar_audio_aula("Aula", "  ", str(tmp_path))


def test_gerar_audio_aula(tmp_path):
    with patch("curso.audio_render.narrar_texto", side_effect=_fake_narrar):
        path = gerar_audio_aula("Embeddings", "Texto da explicação completa da aula.", str(tmp_path))
    assert Path(path).exists()
    assert 1.3 <= medir_duracao_audio(path) <= 1.7


def test_gerar_podcast_aula_sem_falas_falha():
    with pytest.raises(AudioRenderError, match="sem falas"):
        gerar_podcast_aula("Aula", {"turns": []}, "/tmp")


def test_gerar_podcast_aula_alterna_vozes_e_concatena(tmp_path):
    script = {"turns": [
        {"speaker": "A", "text": "Fala 1"},
        {"speaker": "B", "text": "Fala 2"},
        {"speaker": "A", "text": "Fala 3"},
    ]}
    vozes_usadas = []

    def fake_com_registro(texto, out_path, voice="pt-BR-AntonioNeural"):
        vozes_usadas.append(voice)
        return _fake_narrar(texto, out_path, voice, duracao=1.0)

    progresso = []
    with patch("curso.audio_render.narrar_texto", side_effect=fake_com_registro):
        final = gerar_podcast_aula(
            "Aula", script, str(tmp_path),
            progress_callback=lambda i, total: progresso.append((i, total)),
        )

    assert vozes_usadas == ["pt-BR-AntonioNeural", "pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"]
    assert progresso == [(0, 3), (1, 3), (2, 3), (3, 3)]
    assert 2.7 <= medir_duracao_audio(final) <= 3.3  # ~3 x 1s
