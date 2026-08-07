"""tests/test_vertical_export.py — testa tools/vertical_export.py
(build_vertical_command: montagem pura do comando ffmpeg, sem executar
nada). Mexemos nesse arquivo várias vezes hoje (preset, legenda
queimada) só testando na mão — isso formaliza pra não regredir depois."""

import importlib.util
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_vertical_export():
    spec = importlib.util.spec_from_file_location(
        "vertical_export", _PROJECT_ROOT / "tools" / "vertical_export.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_ve = _load_vertical_export()
build_vertical_command = _ve.build_vertical_command


def test_modo_blur_usa_filter_complex():
    cmd = build_vertical_command("in.mp4", "out.mp4", mode="blur")
    assert "-filter_complex" in cmd
    assert "-vf" not in cmd
    idx = cmd.index("-filter_complex")
    assert "boxblur" in cmd[idx + 1]
    assert "overlay" in cmd[idx + 1]


def test_modo_crop_usa_vf_simples():
    cmd = build_vertical_command("in.mp4", "out.mp4", mode="crop")
    assert "-vf" in cmd
    assert "-filter_complex" not in cmd
    idx = cmd.index("-vf")
    assert "crop=1080:1920" in cmd[idx + 1]


def test_preset_padrao_e_medium():
    cmd = build_vertical_command("in.mp4", "out.mp4")
    idx = cmd.index("-preset")
    assert cmd[idx + 1] == "medium"


def test_preset_customizado_fast():
    cmd = build_vertical_command("in.mp4", "out.mp4", preset="fast")
    idx = cmd.index("-preset")
    assert cmd[idx + 1] == "fast"


def test_sem_legenda_nao_injeta_filtro_subtitles():
    cmd = build_vertical_command("in.mp4", "out.mp4", mode="blur")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "subtitles" not in fc


def test_com_legenda_injeta_filtro_subtitles_no_modo_blur():
    cmd = build_vertical_command("in.mp4", "out.mp4", mode="blur",
                                  subtitle_path="/tmp/legenda.srt")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "subtitles=" in fc
    assert "/tmp/legenda.srt" in fc
    # a legenda precisa vir DEPOIS do overlay na cadeia (senão aplicaria
    # antes do vídeo estar montado)
    assert fc.index("overlay") < fc.index("subtitles=")


def test_com_legenda_injeta_filtro_subtitles_no_modo_crop():
    cmd = build_vertical_command("in.mp4", "out.mp4", mode="crop",
                                  subtitle_path="/tmp/legenda.srt")
    vf = cmd[cmd.index("-vf") + 1]
    assert "subtitles=" in vf


def test_caminho_de_legenda_com_dois_pontos_e_escapado():
    """No filtro subtitles= do ffmpeg, ':' é separador de opção — um
    caminho tipo 'C:\\pasta\\legenda.srt' (Windows) ou qualquer caminho
    com ':' precisa vir escapado, senão o ffmpeg interpreta errado."""
    cmd = build_vertical_command("in.mp4", "out.mp4", mode="blur",
                                  subtitle_path="C:/pasta/legenda.srt")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "C\\:/pasta/legenda.srt" in fc


def test_saida_e_ultimo_argumento():
    cmd = build_vertical_command("entrada.mp4", "saida_final.mp4")
    assert cmd[-1] == "saida_final.mp4"


def test_entrada_vem_logo_apos_dash_i():
    cmd = build_vertical_command("meu_video.mp4", "out.mp4")
    idx = cmd.index("-i")
    assert cmd[idx + 1] == "meu_video.mp4"
