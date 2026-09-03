"""tests/test_video_concat.py — testa tools/video_concat.py
(build_concat_command: montagem pura do comando ffmpeg, sem executar
nada — a execução real já foi validada manualmente com o vídeo de
fechamento de verdade do usuário)."""

import importlib.util
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_video_concat():
    spec = importlib.util.spec_from_file_location(
        "video_concat", _PROJECT_ROOT / "tools" / "video_concat.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_vc = _load_video_concat()
build_concat_command = _vc.build_concat_command


def test_ambos_com_audio():
    main_info = {"width": 1080, "height": 1920, "has_audio": True}
    outro_info = {"width": 1280, "height": 720, "has_audio": True}
    cmd = build_concat_command("main.mp4", "outro.mp4", "out.mp4", main_info, outro_info)
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "concat=n=2:v=1:a=1" in fc
    assert "[outv]" in cmd and "[outa]" in cmd
    # não deveria ter entrada extra de anullsrc nesse caso
    assert "anullsrc" not in " ".join(cmd)


def test_fechamento_sem_audio():
    """Fechamento mudo + principal com áudio -> precisa gerar silêncio
    pro fechamento, senão o concat quebra ou perde sincronia."""
    main_info = {"width": 1080, "height": 1920, "has_audio": True}
    outro_info = {"width": 1280, "height": 720, "has_audio": False}
    cmd = build_concat_command("main.mp4", "outro.mp4", "out.mp4", main_info, outro_info)
    assert "anullsrc" in " ".join(cmd)
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "concat=n=2:v=1:a=1" in fc


def test_principal_sem_audio():
    """Principal mudo + fechamento com áudio -> precisa gerar silêncio
    pro principal."""
    main_info = {"width": 1080, "height": 1920, "has_audio": False}
    outro_info = {"width": 1280, "height": 720, "has_audio": True}
    cmd = build_concat_command("main.mp4", "outro.mp4", "out.mp4", main_info, outro_info)
    assert "anullsrc" in " ".join(cmd)


def test_nenhum_tem_audio():
    """Nenhum dos dois tem áudio -> concat só de vídeo (a=0), sem mapear áudio."""
    main_info = {"width": 1080, "height": 1920, "has_audio": False}
    outro_info = {"width": 1280, "height": 720, "has_audio": False}
    cmd = build_concat_command("main.mp4", "outro.mp4", "out.mp4", main_info, outro_info)
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "concat=n=2:v=1:a=0" in fc
    assert "[outa]" not in cmd  # não deveria tentar mapear áudio que não existe


def test_escala_letterbox_preserva_proporcao():
    """O fechamento precisa ser redimensionado SEM distorcer (scale +
    pad), nunca esticado pra encher a tela inteira."""
    main_info = {"width": 1080, "height": 1920, "has_audio": True}
    outro_info = {"width": 1280, "height": 720, "has_audio": True}
    cmd = build_concat_command("main.mp4", "outro.mp4", "out.mp4", main_info, outro_info)
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "force_original_aspect_ratio=decrease" in fc
    assert "pad=1080:1920" in fc


def test_saida_e_ultimo_argumento():
    main_info = {"width": 1080, "height": 1920, "has_audio": True}
    outro_info = {"width": 1280, "height": 720, "has_audio": True}
    cmd = build_concat_command("main.mp4", "outro.mp4", "saida_final.mp4", main_info, outro_info)
    assert cmd[-1] == "saida_final.mp4"


def test_concat_usa_preset_rapido_por_padrao():
    # build_concat_command não lê VIDEO_CONCAT_PRESET (só _prepare_outro_variant
    # lê OUTRO_PRESET, função separada) — o preset do fallback de reencode é
    # fixo "fast" no código. Esse teste tentava desligar uma env var que a
    # função nem consulta; corrigido pra refletir o comportamento real.
    main_info = {"width": 1080, "height": 1920, "has_audio": True}
    outro_info = {"width": 1280, "height": 720, "has_audio": True}
    cmd = build_concat_command("main.mp4", "outro.mp4", "out.mp4", main_info, outro_info)
    assert cmd[cmd.index("-preset") + 1] == "fast"
