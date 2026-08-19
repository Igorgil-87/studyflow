"""
tools/video_concat.py — cola um vídeo de FECHAMENTO/IDENTIDADE no final
de qualquer clip gerado (Shorts ou Cortes). Pensado pra "assinatura" que
o criador quer sempre no final: logo, call-to-action, etc.

O vídeo de fechamento pode ter QUALQUER resolução/proporção — essa
ferramenta redimensiona ele automaticamente pra bater com o clip
principal (escala + faixas pretas, preservando a proporção original do
fechamento, sem esticar/distorcer) antes de colar os dois.
"""

from __future__ import annotations

import json
import os
import subprocess


class VideoConcatError(RuntimeError):
    """Erro ao concatenar vídeos."""


def check_ffmpeg() -> bool:
    import shutil
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def probe_video(path: str) -> dict:
    """Resolução, duração e se tem trilha de áudio — via ffprobe."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_streams", "-show_format", path],
            capture_output=True, text=True, timeout=30, check=True,
        )
        data = json.loads(out.stdout)
    except Exception as e:
        raise VideoConcatError(f"ffprobe falhou em '{path}': {e}") from e

    video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    has_audio = any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    if not video_stream:
        raise VideoConcatError(f"'{path}' não tem trilha de vídeo.")

    return {
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "has_audio": has_audio,
        "duration": float(data.get("format", {}).get("duration", 0) or 0),
    }


def build_concat_command(main_path: str, outro_path: str, output_path: str,
                          main_info: dict, outro_info: dict) -> list[str]:
    """Monta o comando ffmpeg. Puro/testável — não executa nada.

    Redimensiona o fechamento pra CABER dentro da resolução do clip
    principal (scale + pad, preservando proporção original do
    fechamento — sem esticar/distorcer a imagem). Trata o caso do
    fechamento não ter áudio (adiciona trilha muda, senão o concat
    falha ou perde sincronia)."""
    w, h = main_info["width"], main_info["height"]

    # escala o fechamento pra CABER em WxH sem distorcer, preenchendo o
    # resto com preto (letterbox/pillarbox conforme a proporção)
    outro_scale = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30"
    )
    main_scale = f"scale={w}:{h},setsar=1,fps=30"

    inputs = ["-i", main_path, "-i", outro_path]
    filter_parts = [f"[0:v]{main_scale}[v0]", f"[1:v]{outro_scale}[v1]"]

    if main_info["has_audio"] and outro_info["has_audio"]:
        filter_parts.append("[v0][0:a][v1][1:a]concat=n=2:v=1:a=1[outv][outa]")
        map_args = ["-map", "[outv]", "-map", "[outa]"]
    elif main_info["has_audio"] and not outro_info["has_audio"]:
        # fechamento sem áudio -> gera um silêncio do tamanho certo
        inputs += ["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo"]
        filter_parts.append("[v0][0:a][v1][2:a]concat=n=2:v=1:a=1[outv][outa]")
        map_args = ["-map", "[outv]", "-map", "[outa]"]
    elif not main_info["has_audio"] and outro_info["has_audio"]:
        inputs += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        # troca a ordem: silêncio pro clip principal, áudio real pro fechamento
        filter_parts = [f"[0:v]{main_scale}[v0]", f"[1:v]{outro_scale}[v1]"]
        filter_parts.append("[v0][2:a][v1][1:a]concat=n=2:v=1:a=1[outv][outa]")
        map_args = ["-map", "[outv]", "-map", "[outa]"]
    else:
        # nenhum dos dois tem áudio
        filter_parts.append("[v0][v1]concat=n=2:v=1:a=0[outv]")
        map_args = ["-map", "[outv]"]

    filter_complex = ";".join(filter_parts)

    return [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex,
        *map_args,
        "-c:v", "libx264", "-preset", os.getenv("VIDEO_CONCAT_PRESET", "veryfast"), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "44100",
        "-movflags", "+faststart",
        output_path,
    ]


def append_outro(main_path: str, outro_path: str, output_path: str,
                  timeout: int | None = None) -> dict:
    """Executa o ffmpeg de verdade. Retorna {ok, output|erro}.

    O timeout pode ser sobrescrito por chamada. Quando omitido, usa
    VIDEO_CONCAT_TIMEOUT_SECONDS (padrão: 600s). Assim o mesmo código
    funciona localmente e na cloud, mudando só configuração.
    """
    if timeout is None:
        timeout = int(os.getenv("VIDEO_CONCAT_TIMEOUT_SECONDS", "600"))
    if not check_ffmpeg():
        return {"ok": False, "erro": "ffmpeg/ffprobe não encontrado."}

    try:
        main_info = probe_video(main_path)
        outro_info = probe_video(outro_path)
    except VideoConcatError as e:
        return {"ok": False, "erro": str(e)}

    cmd = build_concat_command(main_path, outro_path, output_path, main_info, outro_info)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            return {"ok": False, "erro": f"ffmpeg falhou: {(proc.stderr or '')[-400:]}"}
        return {"ok": True, "output": output_path}
    except subprocess.TimeoutExpired:
        return {"ok": False, "erro": f"ffmpeg demorou mais de {timeout}s (timeout)."}
    except Exception as e:
        return {"ok": False, "erro": f"{type(e).__name__}: {e}"}
