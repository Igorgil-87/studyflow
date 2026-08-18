"""
Configuração central de acesso ao YouTube/yt-dlp.

Objetivos:
- manter cookies, proxy, timeouts e retries iguais em todos os módulos;
- funcionar em servidor headless (Hetzner) com COOKIES_FILE;
- aproveitar o runtime JS externo (Deno recomendado pelo yt-dlp);
- permitir diagnóstico simples sem duplicar lógica.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from tools.cookies_config import get_cookies_file


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "sim"}


def get_proxy_url() -> str:
    return os.getenv("PROXY_URL", "").strip()


def get_cookies_browser() -> str:
    return os.getenv("COOKIES_BROWSER", "").strip()


def get_socket_timeout() -> int:
    try:
        return max(5, int(os.getenv("YTDLP_SOCKET_TIMEOUT", "30")))
    except ValueError:
        return 30


def get_retries() -> int:
    try:
        return max(0, int(os.getenv("YTDLP_RETRIES", "3")))
    except ValueError:
        return 3


def common_ydl_opts(
    *,
    cookies_browser: str | None = None,
    cookies_file: str | None = None,
    use_auth: bool = True,
    use_proxy: bool = True,
    quiet: bool = True,
) -> dict[str, Any]:
    """Opções comuns seguras para qualquer uso de yt-dlp.

    Não define format/outtmpl/extract_flat, pois isso varia por consumidor.
    Cookies de arquivo têm prioridade sobre cookies-from-browser em servidor.
    """
    opts: dict[str, Any] = {
        "quiet": quiet,
        "no_warnings": quiet,
        "socket_timeout": get_socket_timeout(),
        "retries": get_retries(),
        "fragment_retries": get_retries(),
    }

    if use_proxy:
        proxy = get_proxy_url()
        if proxy:
            opts["proxy"] = proxy

    if use_auth:
        cookie_path = (cookies_file if cookies_file is not None else get_cookies_file()).strip()
        browser = (cookies_browser if cookies_browser is not None else get_cookies_browser()).strip()
        if cookie_path and Path(cookie_path).is_file():
            opts["cookiefile"] = cookie_path
        elif browser:
            # Útil em dev local. Em container/headless, prefira COOKIES_FILE.
            opts["cookiesfrombrowser"] = (browser,)

    return opts


def auth_variants(
    *,
    cookies_browser: str | None = None,
    cookies_file: str | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Retorna variantes de autenticação em ordem conservadora.

    1) sem cookies: evita sessão desnecessária quando o vídeo é público;
    2) cookies.txt: recomendado para servidor headless;
    3) cookies do navegador: apenas para desenvolvimento local.

    O proxy, quando configurado, é aplicado a todas as variantes.
    """
    variants: list[tuple[str, dict[str, Any]]] = []
    variants.append(("sem_cookies", common_ydl_opts(use_auth=False)))

    cookie_path = (cookies_file if cookies_file is not None else get_cookies_file()).strip()
    if cookie_path and Path(cookie_path).is_file():
        variants.append((
            "cookies_file",
            common_ydl_opts(cookies_file=cookie_path, cookies_browser="", use_auth=True),
        ))

    browser = (cookies_browser if cookies_browser is not None else get_cookies_browser()).strip()
    if browser:
        variants.append((
            f"cookies_browser={browser}",
            common_ydl_opts(cookies_browser=browser, cookies_file="", use_auth=True),
        ))
    return variants


def executable_version(command: str, *args: str) -> str | None:
    path = shutil.which(command)
    if not path:
        return None
    try:
        proc = subprocess.run(
            [path, *args], capture_output=True, text=True, timeout=10, check=False
        )
        text = (proc.stdout or proc.stderr or "").strip().splitlines()
        return text[0] if text else "installed"
    except Exception:
        return "installed"


def runtime_status() -> dict[str, Any]:
    """Status local usado pelo doctor e por logs de erro."""
    try:
        import yt_dlp
        ytdlp_version = getattr(getattr(yt_dlp, "version", None), "__version__", "unknown")
    except Exception as exc:  # pragma: no cover - diagnóstico
        ytdlp_version = f"unavailable: {exc}"

    cookies = get_cookies_file()
    proxy = get_proxy_url()
    deno_version = executable_version("deno", "--version")
    node_version = executable_version("node", "--version")

    return {
        "yt_dlp": ytdlp_version,
        "ffmpeg": executable_version("ffmpeg", "-version"),
        "ffprobe": executable_version("ffprobe", "-version"),
        "deno": deno_version,
        "node": node_version,
        "js_runtime_ok": bool(deno_version or node_version),
        "cookies_file": cookies or None,
        "cookies_file_exists": bool(cookies and Path(cookies).is_file()),
        "cookies_browser": get_cookies_browser() or None,
        "proxy_configured": bool(proxy),
        "proxy_scheme": proxy.split(":", 1)[0] if proxy else None,
        "socket_timeout": get_socket_timeout(),
        "retries": get_retries(),
        "allow_live_network_doctor": _env_bool("YOUTUBE_DOCTOR_NETWORK", False),
    }
