"""tests/test_video_render.py — cobre curso/video_render.py.

render_diagram_scene / ffmpeg (medir_duracao_audio, montar_clipe_estatico,
concatenar_clipes, gerar_video_aula) rodam com ffmpeg DE VERDADE — só a
narração (edge-tts, precisa de rede pra Microsoft) é mockada, substituída
por um tom sintético gerado com ffmpeg (sine wave), que serve igualmente
bem pra testar duração/composição/concatenação sem depender de rede.
"""

import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="ffmpeg/ffprobe não disponíveis neste ambiente",
)

from curso.video_render import (  # noqa: E402
    VideoRenderError, concatenar_clipes, gerar_video_aula,
    medir_duracao_audio, montar_clipe_estatico, render_diagram_scene,
)


def _tom_sintetico(path: str, duracao: float) -> str:
    """Gera um áudio de teste (tom puro) via ffmpeg — substitui o TTS
    real (edge-tts precisa de rede) nos testes de composição/duração."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=440:duration={duracao}",
         "-ar", "24000", path],
        capture_output=True, check=True,
    )
    return path


def test_render_diagram_scene_gera_png_valido(tmp_path):
    out = render_diagram_scene(
        "Embeddings: representação vetorial\n- Captura significado\n- Base de busca vetorial",
        str(tmp_path / "cena.png"),
    )
    with open(out, "rb") as f:
        assert f.read(8) == b"\x89PNG\r\n\x1a\n"


def test_render_diagram_scene_aceita_texto_em_uma_linha_so(tmp_path):
    """StoryboardAgent pode mandar tudo numa linha — não pode quebrar."""
    out = render_diagram_scene(
        "Título da cena. Primeiro ponto. Segundo ponto.", str(tmp_path / "cena.png")
    )
    with open(out, "rb") as f:
        assert f.read(8) == b"\x89PNG\r\n\x1a\n"


def test_medir_duracao_audio(tmp_path):
    audio = _tom_sintetico(str(tmp_path / "tom.mp3"), 3.0)
    duracao = medir_duracao_audio(audio)
    assert 2.9 <= duracao <= 3.1


def test_montar_clipe_estatico_duracao_bate_com_audio(tmp_path):
    img = render_diagram_scene("Cena\n- ponto", str(tmp_path / "cena.png"))
    audio = _tom_sintetico(str(tmp_path / "audio.mp3"), 2.5)
    clipe = montar_clipe_estatico(img, audio, str(tmp_path / "clipe.mp4"))
    assert 2.3 <= medir_duracao_audio(clipe) <= 2.7


def test_concatenar_clipes_soma_duracoes(tmp_path):
    img = render_diagram_scene("Cena\n- ponto", str(tmp_path / "cena.png"))
    audio1 = _tom_sintetico(str(tmp_path / "a1.mp3"), 3.0)
    audio2 = _tom_sintetico(str(tmp_path / "a2.mp3"), 2.0)
    clipe1 = montar_clipe_estatico(img, audio1, str(tmp_path / "c1.mp4"))
    clipe2 = montar_clipe_estatico(img, audio2, str(tmp_path / "c2.mp4"))

    final = concatenar_clipes([clipe1, clipe2], str(tmp_path / "final.mp4"))
    duracao = medir_duracao_audio(final)
    assert 4.7 <= duracao <= 5.3  # ~3 + 2


def test_concatenar_clipes_lista_vazia_falha():
    with pytest.raises(VideoRenderError):
        concatenar_clipes([], "/tmp/nao_importa.mp4")


def test_gerar_video_aula_orquestra_tudo(tmp_path, monkeypatch):
    storyboard = {
        "scenes": [
            {"tipo": "diagrama", "narration": "Primeira narração.",
             "visual_description": "Cena 1\n- ponto A", "duration_seconds": 3},
            {"tipo": "diagrama", "narration": "Segunda narração.",
             "visual_description": "Cena 2\n- ponto B", "duration_seconds": 2},
        ]
    }

    def fake_narrar(texto, out_path, voice="pt-BR-AntonioNeural"):
        return _tom_sintetico(out_path, 2.0)

    monkeypatch.setattr("curso.video_render.narrar_cena", fake_narrar)

    progresso = []
    final = gerar_video_aula(
        "Aula Teste", storyboard, str(tmp_path),
        progress_callback=lambda i, total: progresso.append((i, total)),
    )

    assert final.endswith("final.mp4")
    assert progresso == [(0, 2), (1, 2), (2, 2)]
    assert medir_duracao_audio(final) > 3.5  # ~2+2 segundos de cena


def test_gerar_video_aula_sem_cenas_falha():
    with pytest.raises(VideoRenderError):
        gerar_video_aula("Aula", {"scenes": []}, "/tmp")
