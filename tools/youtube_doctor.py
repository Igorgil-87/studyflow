"""Diagnóstico da camada YouTube do StudyFlow.

Uso:
    python -m tools.youtube_doctor
    YOUTUBE_DOCTOR_NETWORK=1 python -m tools.youtube_doctor --url https://www.youtube.com/watch?v=VIDEO_ID

O doctor não imprime PROXY_URL nem credenciais. O teste de rede opcional usa
as mesmas opções centralizadas do aplicativo (proxy/cookies/POT provider).
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
            probe = {
                "ok": None,
                "skipped": "defina YOUTUBE_DOCTOR_NETWORK=1 para habilitar teste externo",
            }

    payload = {"runtime": status, "metadata_probe": probe}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print("StudyFlow YouTube Doctor")
    print("=" * 46)
    print(f"yt-dlp ........... {status['yt_dlp']}")
    print(f"ffmpeg ........... {_ok(bool(status['ffmpeg']))}  {status['ffmpeg'] or 'não encontrado'}")
    print(f"ffprobe .......... {_ok(bool(status['ffprobe']))}  {status['ffprobe'] or 'não encontrado'}")
    print(f"Deno ............. {_ok(bool(status['deno']))}  {status['deno'] or 'não encontrado'}")
    print(f"Node ............. {'OK' if status['node'] else 'opcional'}  {status['node'] or 'não encontrado'}")
    print(f"JS runtime ....... {_ok(status['js_runtime_ok'])}")
    print(
        "cookies.txt ...... "
        f"{'OK' if status['cookies_file_exists'] else 'não configurado'}  "
        f"{status['cookies_file'] or ''}"
    )
    print(f"cookies browser .. {status['cookies_browser'] or 'não configurado'}")
    print(f"proxy ............ {'configurado' if status['proxy_configured'] else 'desabilitado'}")

    plugin = status["pot_provider_plugin"]
    provider_config = status["pot_provider_configured"]
    reachable = status["pot_provider_reachable"]
    print(f"POT plugin ....... {'OK ' + plugin if plugin else 'AUSENTE'}")
    if not provider_config:
        print("POT provider ..... não configurado")
    elif reachable:
        print("POT provider ..... OK  alcançável pela rede Docker")
    else:
        print("POT provider ..... WARN  configurado, mas porta não alcançável")
    print(f"player clients ... {status['player_clients'] or 'padrão do yt-dlp'}")
    print(f"socket timeout ... {status['socket_timeout']}s")
    print(f"retries .......... {status['retries']}")

    if probe is not None:
        if probe.get("ok") is True:
            print(f"metadata test .... PASS  {probe.get('title', '')}")
        elif probe.get("ok") is False:
            print(f"metadata test .... FAIL  {probe.get('error', '')[:300]}")
        else:
            print(f"metadata test .... SKIP  {probe.get('skipped', '')}")

    critical = (
        not status["ffmpeg"]
        or not status["js_runtime_ok"]
        or (provider_config and (not plugin or reachable is False))
    )
    return 1 if critical else 0


if __name__ == "__main__":
    sys.exit(main())
