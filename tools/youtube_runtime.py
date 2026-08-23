"""
Configuração central de acesso ao YouTube/yt-dlp.

Objetivos:
- manter cookies, proxy, timeouts e retries iguais em todos os módulos;
- funcionar em servidor headless (Hetzner) com COOKIES_FILE;
- aproveitar Deno/EJS para os desafios JavaScript atuais do YouTube;
- integrar um PO Token Provider (BgUtils) para formatos GVS que retornam 403;
- permitir diagnóstico simples sem duplicar lógica.
"""
from __future__ import annotations

import importlib.metadata
import os
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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


def get_pot_provider_url() -> str:
    """URL HTTP interna do servidor BgUtils PO Token Provider.

    Em produção, o docker-compose aponta para http://bgutil-pot:4416.
    Vazio desabilita a integração e mantém desenvolvimento local compatível.
    """
    return os.getenv("YTDLP_POT_PROVIDER_URL", "").strip().rstrip("/")


def get_player_clients() -> str:
    """Clientes preferidos quando há PO Token Provider.

    O guia atual do yt-dlp recomenda mweb + PO Token Provider para GVS.
    Mantemos apenas mweb no caminho principal para evitar misturar clients
    com requisitos de token diferentes. web_safari continua disponível como
    fallback explícito nos downloaders quando necessário.
    """
    return os.getenv("YTDLP_PLAYER_CLIENTS", "mweb").strip()


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


def _merge_extractor_args(
    base: dict[str, dict[str, list[str]]] | None,
    extra: dict[str, dict[str, list[str]]],
) -> dict[str, dict[str, list[str]]]:
    merged: dict[str, dict[str, list[str]]] = {}
    for source in (base or {}, extra):
        for extractor, values in source.items():
            merged.setdefault(extractor, {})
            merged[extractor].update(values)
    return merged


def youtube_extractor_args(*, force_client: str | None = None) -> dict[str, dict[str, list[str]]]:
    """Monta extractor_args para YouTube e para o PO Token Provider.

    O plugin bgutil-ytdlp-pot-provider registra o extractor namespace
    ``youtubepot-bgutilhttp``. Quando a URL do provider está configurada,
    direcionamos o plugin ao serviço Docker e preferimos o cliente mweb,
    atualmente recomendado pelo guia oficial do yt-dlp para GVS POT.
    """
    args: dict[str, dict[str, list[str]]] = {}
    provider_url = get_pot_provider_url()

    client = (force_client or (get_player_clients() if provider_url else "")).strip()
    if client:
        args.setdefault("youtube", {})["player_client"] = [client]

    if provider_url:
        args.setdefault("youtubepot-bgutilhttp", {})["base_url"] = [provider_url]

    return args


def with_youtube_client(opts: dict[str, Any], player_client: str) -> dict[str, Any]:
    """Retorna cópia de opts forçando um player_client específico.

    Útil para fallback HLS/web_safari sem perder base_url do POT provider.
    """
    copied = dict(opts)
    copied["extractor_args"] = _merge_extractor_args(
        copied.get("extractor_args"), youtube_extractor_args(force_client=player_client)
    )
    return copied


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
    PO Token Provider e player clients são aplicados centralmente.
    """
    opts: dict[str, Any] = {
        "quiet": quiet,
        "no_warnings": quiet,
        "socket_timeout": get_socket_timeout(),
        "retries": get_retries(),
        "fragment_retries": get_retries(),
    }

    extractor_args = youtube_extractor_args()
    if extractor_args:
        opts["extractor_args"] = extractor_args

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
    3) cookies do navegador: somente se NÃO houver cookies.txt válido.

    O proxy e PO Token Provider, quando configurados, valem para todas.
    """
    variants: list[tuple[str, dict[str, Any]]] = []
    variants.append(("sem_cookies", common_ydl_opts(use_auth=False)))

    cookie_path = (cookies_file if cookies_file is not None else get_cookies_file()).strip()
    has_cookie_file = bool(cookie_path and Path(cookie_path).is_file())
    if has_cookie_file:
        variants.append((
            "cookies_file",
            common_ydl_opts(cookies_file=cookie_path, cookies_browser="", use_auth=True),
        ))

    browser = (cookies_browser if cookies_browser is not None else get_cookies_browser()).strip()
    if browser and not has_cookie_file:
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


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None
    except Exception:
        return "installed"


def _tcp_reachable(url: str, timeout: float = 1.5) -> bool | None:
    """Verifica apenas conectividade TCP; não depende de endpoint /health."""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not host:
            return False
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


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
    provider_url = get_pot_provider_url()
    provider_plugin = _package_version("bgutil-ytdlp-pot-provider")

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
        "pot_provider_url": provider_url or None,
        "pot_provider_plugin": provider_plugin,
        "pot_provider_configured": bool(provider_url),
        "pot_provider_reachable": _tcp_reachable(provider_url),
        "player_clients": get_player_clients() if provider_url else None,
        "socket_timeout": get_socket_timeout(),
        "retries": get_retries(),
        "allow_live_network_doctor": _env_bool("YOUTUBE_DOCTOR_NETWORK", False),
    }
