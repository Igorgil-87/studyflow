"""
tools/vertical_export.py — exporta um clip em formato SHORT 9:16 (1080×1920).

Usa ffmpeg para reenquadrar o corte (que sai no formato original, geralmente
16:9) em vertical, com as specs de Short:
  - 1080×1920, 9:16
  - H.264 (libx264), pix_fmt yuv420p
  - AAC 48kHz 320kbps
  - bitrate alvo 10 Mbps / máx 16 Mbps, 30 fps

Dois modos de reenquadre:
  - "blur"  : vídeo centralizado com fundo desfocado preenchendo topo/baixo
              (melhor p/ podcast/entrevista — não corta o rosto). PADRÃO.
  - "crop"  : recorta o centro para preencher a tela toda (dá zoom).

Requer ffmpeg instalado. check_ffmpeg() detecta.
"""

from __future__ import annotations

import os
import shutil
import subprocess


def check_ffmpeg() -> bool:
    """True se o ffmpeg está disponível no PATH."""
    return shutil.which("ffmpeg") is not None


def _is_safe_cli_path(path: str) -> bool:
    """Bloqueia dois vetores de injeção de linha de comando:
    1) começar com '-' — o ffmpeg (e qualquer CLI) pode interpretar o
       'arquivo' como uma FLAG em vez de um caminho (ex: um nome de
       arquivo literal "-rf" vira opção, não path).
    2) '..' no caminho normalizado — path traversal."""
    normalized = os.path.normpath(path)
    if normalized.startswith("-"):
        return False
    if normalized.startswith(".." + os.sep) or normalized == "..":
        return False
    return True


def _escape_subtitle_path(path: str) -> str:
    """Escapa o caminho do .srt pro filtro subtitles= do ffmpeg — ele usa
    ':' como separador de opção dentro do filtro, então caminho com ':'
    (ex: 'C:\\...' no Windows, ou só por precaução) precisa escapar."""
    return path.replace("\\", "\\\\").replace(":", "\\:")


def build_vertical_command(input_path: str, output_path: str, mode: str = "blur",
                           fps: int = 30, target_bitrate: str = "10M",
                           max_bitrate: str = "16M",
                           subtitle_path: str | None = None,
                           preset: str = "medium") -> list[str]:
    """Monta o comando ffmpeg (lista de args). Puro/testável.

    preset: velocidade x compressão do x264 ("medium" = padrão/melhor
    compressão; "fast"/"veryfast" = roda mais rápido, útil quando vários
    clips são processados em paralelo — a perda de qualidade é mínima
    pro tipo de vídeo comprimido de novo pelo Instagram/TikTok mesmo.

    subtitle_path: caminho de um arquivo .srt já pronto (ver tools/captions.py)
    — se informado, a legenda é queimada no vídeo (fica parte da imagem,
    funciona em qualquer player/plataforma). Estilo: branco, negrito,
    contorno preto, ancorada perto do centro-inferior (boa posição pra
    Reels/Shorts sem cobrir os controles da UI do app)."""
    sub_filter = ""
    if subtitle_path:
        esc = _escape_subtitle_path(subtitle_path)
        # Fontsize/Outline calibrados pro canvas de saída (1080x1920).
        # Alignment=2 = centralizado horizontal, ancorado embaixo.
        # MarginV empurra pra cima da barra de ações do IG/TikTok.
        style = (
            "FontName=Arial,Fontsize=20,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BorderStyle=1,Outline=2.5,Shadow=0,"
            "Bold=1,Alignment=2,MarginV=180"
        )
        sub_filter = f",subtitles='{esc}':force_style='{style}'"

    if mode == "crop":
        # recorta o centro para 9:16 e escala para 1080x1920
        vf = ("scale=1080:1920:force_original_aspect_ratio=increase,"
              "crop=1080:1920" + sub_filter)
        filter_args = ["-vf", vf]
    else:  # blur (padrão): fundo desfocado + vídeo centralizado
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
                    preset: str = "medium") -> dict:
    """Executa o ffmpeg. Retorna {ok, output|erro}."""
    if not check_ffmpeg():
        return {"ok": False, "erro": "ffmpeg não encontrado. Instale o ffmpeg "
                "(macOS: 'brew install ffmpeg')."}
    if not _is_safe_cli_path(input_path) or not _is_safe_cli_path(output_path):
        return {"ok": False, "erro": "caminho de entrada/saída inválido."}
    cmd = build_vertical_command(input_path, output_path, mode,
                                  subtitle_path=subtitle_path, preset=preset)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            tail = (proc.stderr or "")[-400:]
            return {"ok": False, "erro": f"ffmpeg falhou: {tail}"}
        return {"ok": True, "output": output_path}
    except subprocess.TimeoutExpired:
        return {"ok": False, "erro": "ffmpeg demorou demais (timeout)."}
    except Exception as e:
        return {"ok": False, "erro": f"{type(e).__name__}: {e}"}
