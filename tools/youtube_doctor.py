"""Diagnóstico da camada YouTube do StudyFlow.

Uso:
    python -m tools.youtube_doctor
    python -m tools.youtube_doctor --url https://www.youtube.com/watch?v=VIDEO_ID

Por padrão não faz chamada externa. Para permitir teste de metadata:
    YOUTUBE_DOCTOR_NETWORK=1 python -m tools.youtube_doctor --url ...
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from tools.youtube_runtime import common_ydl_opts, runtime_status


def _ok(value: bool) -> str:
    return "OK" if value else "WARN"


def metadata_probe(url: str) -> dict:
    import yt_dlp

    opts = common_ydl_opts(quiet=True)
    opts.update({"skip_download": True, "noplaylist": True})
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {
            "ok": True,
            "id": info.get("id"),
            "title": info.get("title"),
            "duration": info.get("duration"),
            "extractor": info.get("extractor"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="StudyFlow YouTube Doctor")
    parser.add_argument("--url", default="", help="URL opcional para testar extração de metadata")
    parser.add_argument("--json", action="store_true", help="Imprime JSON")
    args = parser.parse_args()

    status = runtime_status()
    probe = None
    if args.url:
        if os.getenv("YOUTUBE_DOCTOR_NETWORK", "").strip().lower() in {"1", "true", "yes", "on"}:
            probe = metadata_probe(args.url)
        else:
            probe = {"ok": None, "skipped": "defina YOUTUBE_DOCTOR_NETWORK=1 para habilitar teste externo"}

    payload = {"runtime": status, "metadata_probe": probe}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print("StudyFlow YouTube Doctor")
    print("=" * 42)
    print(f"yt-dlp ........... {status['yt_dlp']}")
    print(f"ffmpeg ........... {_ok(bool(status['ffmpeg']))}  {status['ffmpeg'] or 'não encontrado'}")
    print(f"ffprobe .......... {_ok(bool(status['ffprobe']))}  {status['ffprobe'] or 'não encontrado'}")
    print(f"Deno ............. {_ok(bool(status['deno']))}  {status['deno'] or 'não encontrado'}")
    print(f"Node ............. {'OK' if status['node'] else 'opcional'}  {status['node'] or 'não encontrado'}")
    print(f"JS runtime ....... {_ok(status['js_runtime_ok'])}")
    print(f"cookies.txt ...... {'OK' if status['cookies_file_exists'] else 'não configurado'}  {status['cookies_file'] or ''}")
    print(f"cookies browser .. {status['cookies_browser'] or 'não configurado'}")
    print(f"proxy ............ {'configurado' if status['proxy_configured'] else 'desabilitado'}")
    print(f"socket timeout ... {status['socket_timeout']}s")
    print(f"retries .......... {status['retries']}")

    if probe is not None:
        if probe.get("ok") is True:
            print(f"metadata test .... PASS  {probe.get('title', '')}")
        elif probe.get("ok") is False:
            print(f"metadata test .... FAIL  {probe.get('error', '')[:300]}")
        else:
            print(f"metadata test .... SKIP  {probe.get('skipped', '')}")

    critical = not status["ffmpeg"] or not status["js_runtime_ok"]
    return 1 if critical else 0


if __name__ == "__main__":
    sys.exit(main())
