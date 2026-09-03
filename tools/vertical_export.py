"""
tools/vertical_export.py — exporta um clip em formato SHORT 9:16 (1080×1920).

Performance Sprint 2:
- o fundo desfocado é processado em resolução reduzida e só então ampliado;
  como ele é propositalmente desfocado, isso reduz drasticamente pixels no
  filtro sem alterar a resolução/qualidade do vídeo principal;
- saída continua H.264 1080x1920/30fps + AAC, pronta para Shorts/Reels;
- preset permanece configurável e o padrão continua ``fast``.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess


def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


_SAFE_CLI_PATH_RE = re.compile(r"^[A-Za-z0-9_./ -]+$")


def _is_safe_cli_path(path: str) -> bool:
    if not _SAFE_CLI_PATH_RE.fullmatch(path):
        return False
    normalized = os.path.normpath(path)
    if normalized.startswith("-"):
        return False
    if normalized.startswith(".." + os.sep) or normalized == "..":
        return False
    return True


def _escape_subtitle_path(path: str) -> str:
    return path.replace("\\", "\\\\").replace(":", "\\:")


def _fast_blur_enabled() -> bool:
    return os.getenv("VERTICAL_FAST_BLUR", "1").strip().lower() not in ("0", "false", "no", "off")


def build_vertical_command(input_path: str, output_path: str, mode: str = "blur",
                           fps: int = 30, target_bitrate: str = "10M",
                           max_bitrate: str = "16M",
                           subtitle_path: str | None = None,
                           preset: str = "fast",
                           fast_blur: bool | None = None) -> list[str]:
    """Monta o comando ffmpeg (lista de args). Puro/testável.

    ``fast_blur`` otimiza apenas a camada de FUNDO. O foreground continua
    escalado diretamente para a resolução final. O ganho vem de não executar
    boxblur em ~2 milhões de pixels por frame quando o resultado será borrado.
    """
    sub_filter = ""
    if subtitle_path:
        esc = _escape_subtitle_path(subtitle_path)
        style = (
            "FontName=Arial,Fontsize=20,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BorderStyle=1,Outline=2.5,Shadow=0,"
            "Bold=1,Alignment=2,MarginV=180"
        )
        sub_filter = f",subtitles='{esc}':force_style='{style}'"

    if mode == "crop":
        vf = ("scale=1080:1920:force_original_aspect_ratio=increase,"
              "crop=1080:1920" + sub_filter)
        filter_args = ["-vf", vf]
    else:
        if fast_blur is None:
            fast_blur = _fast_blur_enabled()
        if fast_blur:
            # Background propositalmente desfocado: trabalha em 270x480
            # (1/16 dos pixels do canvas final), aplica blur e só então sobe
            # para 1080x1920. O foreground permanece em resolução cheia.
            fc = (
                "[0:v]scale=270:480:force_original_aspect_ratio=increase,"
                "crop=270:480,boxblur=12:4,scale=1080:1920[bg];"
                "[0:v]scale=1080:-2:force_original_aspect_ratio=decrease[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2" + sub_filter
            )
        else:
            fc = (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                "crop=1080:1920,boxblur=24:6[bg];"
                "[0:v]scale=1080:-2:force_original_aspect_ratio=decrease[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2" + sub_filter
            )
        filter_args = ["-filter_complex", fc]

    bufsize = f"{int(max_bitrate.rstrip('M')) * 2}M"
    return [
        "ffmpeg", "-y", "-i", input_path,
        *filter_args,
        "-c:v", "libx264", "-preset", preset, "-profile:v", "high",
        "-pix_fmt", "yuv420p",
        "-b:v", target_bitrate, "-maxrate", max_bitrate, "-bufsize", bufsize,
        "-r", str(fps),
        "-c:a", "aac", "-ar", "48000", "-b:a", "320k", "-ac", "2",
        "-movflags", "+faststart",
        output_path,
    ]


def export_vertical(input_path: str, output_path: str, mode: str = "blur",
                    timeout: int = 600, subtitle_path: str | None = None,
                    preset: str | None = None,
                    fast_blur: bool | None = None) -> dict:
    """Executa o ffmpeg. Retorna {ok, output|erro}."""
    if not check_ffmpeg():
        return {"ok": False, "erro": "ffmpeg não encontrado. Instale o ffmpeg "
                "(macOS: 'brew install ffmpeg')."}
    for _p in (input_path, output_path):
        if not _is_safe_cli_path(_p):
            return {"ok": False, "erro": "caminho de entrada/saída inválido."}
    if preset is None:
        preset = os.getenv("VERTICAL_PRESET", "fast").strip() or "fast"
    cmd = build_vertical_command(input_path, output_path, mode,
                                  subtitle_path=subtitle_path, preset=preset,
                                  fast_blur=fast_blur)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            tail = (proc.stderr or "")[-400:]
            return {"ok": False, "erro": f"ffmpeg falhou: {tail}"}
        return {"ok": True, "output": output_path, "preset": preset,
                "fast_blur": _fast_blur_enabled() if fast_blur is None else bool(fast_blur)}
    except subprocess.TimeoutExpired:
        return {"ok": False, "erro": "ffmpeg demorou demais (timeout)."}
    except Exception as e:
        return {"ok": False, "erro": f"{type(e).__name__}: {e}"}
