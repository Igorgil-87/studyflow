"""
tools/video_concat.py — cola vídeo de fechamento/identidade no clip final.

Performance Sprint 2:
O caminho antigo reencodava TODO o Short uma segunda vez apenas para anexar
um fechamento de poucos segundos. Isso dobrava boa parte do custo do vertical.

Agora, quando possível:
1. normaliza o fechamento uma única vez para os mesmos parâmetros do clip;
2. guarda essa variante em cache;
3. concatena clip + fechamento com stream-copy (``-c copy``), sem reencodar
   o vídeo principal;
4. se qualquer incompatibilidade ocorrer, faz fallback automático para o
   método antigo de reencode. Qualidade e compatibilidade vencem performance.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path


class VideoConcatError(RuntimeError):
    pass


def check_ffmpeg() -> bool:
    import shutil
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def probe_video(path: str) -> dict:
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
    audio_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not video_stream:
        raise VideoConcatError(f"'{path}' não tem trilha de vídeo.")

    return {
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "video_codec": video_stream.get("codec_name") or "",
        "pix_fmt": video_stream.get("pix_fmt") or "",
        "has_audio": audio_stream is not None,
        "audio_codec": (audio_stream or {}).get("codec_name") or "",
        "sample_rate": int((audio_stream or {}).get("sample_rate") or 48000),
        "channels": int((audio_stream or {}).get("channels") or 2),
        "duration": float(data.get("format", {}).get("duration", 0) or 0),
    }


def build_concat_command(main_path: str, outro_path: str, output_path: str,
                         main_info: dict, outro_info: dict) -> list[str]:
    """Fallback compatível: reencoda os dois vídeos e concatena."""
    w, h = main_info["width"], main_info["height"]
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
        inputs += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        filter_parts.append("[v0][0:a][v1][2:a]concat=n=2:v=1:a=1[outv][outa]")
        map_args = ["-map", "[outv]", "-map", "[outa]"]
    elif not main_info["has_audio"] and outro_info["has_audio"]:
        inputs += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        filter_parts.append("[v0][2:a][v1][1:a]concat=n=2:v=1:a=1[outv][outa]")
        map_args = ["-map", "[outv]", "-map", "[outa]"]
    else:
        filter_parts.append("[v0][v1]concat=n=2:v=1:a=0[outv]")
        map_args = ["-map", "[outv]"]

    return [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(filter_parts),
        *map_args,
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", str(main_info.get("sample_rate") or 48000),
        "-movflags", "+faststart",
        output_path,
    ]


def _fast_concat_enabled() -> bool:
    return os.getenv("OUTRO_FAST_CONCAT", "1").strip().lower() not in ("0", "false", "no", "off")


def _variant_cache_path(outro_path: str, main_info: dict) -> str:
    st = os.stat(outro_path)
    signature = "|".join([
        os.path.abspath(outro_path), str(st.st_mtime_ns), str(st.st_size),
        str(main_info["width"]), str(main_info["height"]),
        str(bool(main_info["has_audio"])), str(main_info.get("sample_rate") or 48000),
        str(main_info.get("channels") or 2),
    ])
    digest = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:16]
    cache_dir = Path(os.getenv("OUTRO_CACHE_DIR", "static/video/.cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    return str(cache_dir / f"outro_{digest}.mp4")


def _prepare_outro_variant(outro_path: str, main_info: dict, timeout: int = 120) -> str:
    cached = _variant_cache_path(outro_path, main_info)
    if os.path.exists(cached) and os.path.getsize(cached) > 1024:
        return cached

    w, h = main_info["width"], main_info["height"]
    sr = int(main_info.get("sample_rate") or 48000)
    channels = int(main_info.get("channels") or 2)
    channel_layout = "mono" if channels == 1 else "stereo"
    outro_info = probe_video(outro_path)

    cmd = ["ffmpeg", "-y", "-i", outro_path]
    if main_info["has_audio"] and not outro_info["has_audio"]:
        cmd += ["-f", "lavfi", "-i", f"anullsrc=r={sr}:cl={channel_layout}"]

    vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
          f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30")
    cmd += ["-map", "0:v:0"]
    if main_info["has_audio"]:
        if outro_info["has_audio"]:
            cmd += ["-map", "0:a:0"]
        else:
            cmd += ["-map", "1:a:0", "-shortest"]
    cmd += [
        "-vf", vf,
        "-c:v", "libx264", "-preset", os.getenv("OUTRO_PRESET", "fast"),
        "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-b:v", "10M", "-maxrate", "16M", "-bufsize", "32M", "-r", "30",
    ]
    if main_info["has_audio"]:
        cmd += ["-c:a", "aac", "-ar", str(sr), "-ac", str(channels), "-b:a", "320k"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart", cached]

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        try:
            os.remove(cached)
        except OSError:
            pass
        raise VideoConcatError(f"normalização do fechamento falhou: {(proc.stderr or '')[-400:]}")
    return cached


def _escape_concat_path(path: str) -> str:
    # Sintaxe do concat demuxer: file '...'. Aspas simples internas precisam
    # da sequência padrão do parser ffmpeg.
    return os.path.abspath(path).replace("'", "'\\''")


def _concat_stream_copy(main_path: str, normalized_outro: str, output_path: str,
                        timeout: int = 60) -> None:
    manifest_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as manifest:
            manifest.write(f"file '{_escape_concat_path(main_path)}'\n")
            manifest.write(f"file '{_escape_concat_path(normalized_outro)}'\n")
            manifest_path = manifest.name
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", manifest_path,
            "-c", "copy", "-movflags", "+faststart", output_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            raise VideoConcatError(f"concat stream-copy falhou: {(proc.stderr or '')[-400:]}")
    finally:
        if manifest_path:
            try:
                os.remove(manifest_path)
            except OSError:
                pass


def append_outro(main_path: str, outro_path: str, output_path: str,
                  timeout: int = 180) -> dict:
    """Anexa fechamento. Fast path sem reencode + fallback seguro."""
    if not check_ffmpeg():
        return {"ok": False, "erro": "ffmpeg/ffprobe não encontrado."}

    try:
        main_info = probe_video(main_path)
        outro_info = probe_video(outro_path)
    except VideoConcatError as e:
        return {"ok": False, "erro": str(e)}

    # O fast path é especialmente valioso para Shorts já finalizados em H.264.
    if _fast_concat_enabled() and main_info.get("video_codec") == "h264":
        try:
            normalized = _prepare_outro_variant(outro_path, main_info)
            _concat_stream_copy(main_path, normalized, output_path, timeout=min(timeout, 90))
            return {"ok": True, "output": output_path, "mode": "stream_copy", "outro_variant": normalized}
        except Exception as e:
            print(f"[video_concat] fast path falhou; fallback reencode: {e}")
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
            except OSError:
                pass

    cmd = build_concat_command(main_path, outro_path, output_path, main_info, outro_info)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            return {"ok": False, "erro": f"ffmpeg falhou: {(proc.stderr or '')[-400:]}"}
        return {"ok": True, "output": output_path, "mode": "reencode_fallback"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "erro": "ffmpeg demorou demais (timeout)."}
    except Exception as e:
        return {"ok": False, "erro": f"{type(e).__name__}: {e}"}
