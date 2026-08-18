"""
tools/video_downloader.py
Baixa vídeo do YouTube para reprodução local na interface.

Produção 2026:
- proxy residencial via PROXY_URL para evitar bloqueio de IP de datacenter;
- cookies.txt via COOKIES_FILE para autenticação headless;
- Deno/EJS para JavaScript challenges;
- PO Token Provider (BgUtils) para GVS/HTTP 403;
- fallback web_safari/HLS quando formatos HTTPS/DASH continuam rejeitados.
"""

import glob
import os
import time
from pathlib import Path

import yt_dlp
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from tools.youtube_runtime import common_ydl_opts, with_youtube_client


class VideoDownloaderInput(BaseModel):
    url: str = Field(description="URL completa do vídeo do YouTube")


class VideoDownloaderTool(BaseTool):
    name: str = "video_downloader"
    description: str = (
        "Baixa o vídeo do YouTube em .mp4 para reprodução local. "
        "Retorna o caminho do arquivo de vídeo. Use após escolher o vídeo."
    )
    args_schema: type[BaseModel] = VideoDownloaderInput
    output_dir: str = "static/videos"
    cookies_browser: str = ""
    cookies_file: str = ""

    def _base_opts(
        self,
        out_template: str,
        *,
        use_auth: bool = False,
        cookies_browser: str = "",
        cookies_file: str = "",
    ) -> dict:
        opts = common_ydl_opts(
            cookies_browser=cookies_browser,
            cookies_file=cookies_file,
            use_auth=use_auth,
            quiet=True,
        )
        opts.update({
            # Mantém compatibilidade com navegador e limita custo/banda.
            # Se não houver combinação MP4/M4A, permite fallback geral.
            "format": (
                "bv*[height<=720][ext=mp4]+ba[ext=m4a]/"
                "b[height<=720][ext=mp4]/"
                "best[height<=720]/best"
            ),
            "outtmpl": out_template,
            "merge_output_format": "mp4",
            "continuedl": False,
            "nopart": True,
        })
        return opts

    def _hls_fallback_opts(self, opts: dict) -> dict:
        """Fallback deliberado para web_safari/HLS.

        O guia atual do yt-dlp informa que HLS do web_safari pode continuar
        disponível em cenários onde GVS HTTPS/DASH exige PO Token. Mantemos
        isto como segunda tentativa, não como caminho principal.
        """
        fallback = with_youtube_client(opts, "web_safari")
        fallback["format"] = (
            "best[protocol^=m3u8][height<=720]/"
            "best[height<=720]/best"
        )
        return fallback

    @staticmethod
    def _try_download(url: str, opts: dict) -> str | None:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            return None
        except Exception as exc:
            return str(exc)

    @staticmethod
    def _clean_job_files(output_path: Path, base_name: str) -> None:
        for leftover in glob.glob(str(output_path / f"{base_name}.*")):
            try:
                os.remove(leftover)
            except OSError:
                pass

    def _run(self, url: str, progress_callback=None, job_id: str | None = None) -> str:
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        base_name = f"current_video_{job_id}" if job_id else "current_video"
        out_template = str(output_path / f"{base_name}.%(ext)s")
        final_video = str(output_path / f"{base_name}.mp4")
        self._clean_job_files(output_path, base_name)

        last_emit = [0.0]

        def _hook(d):
            if not progress_callback or d.get("status") != "downloading":
                return
            now = time.time()
            if now - last_emit[0] < 2.0:
                return
            last_emit[0] = now
            pct = (d.get("_percent_str") or "").strip()
            speed = (d.get("_speed_str") or "").strip()
            eta = (d.get("_eta_str") or "").strip()
            progress_callback(f"{pct} a {speed} · ETA {eta}".strip(" ·"))

        # O cookies.txt tem precedência sobre cookies-from-browser em headless.
        auth_configs: list[tuple[str, dict]] = []

        opts_public = self._base_opts(out_template, use_auth=False)
        auth_configs.append(("sem_cookies", opts_public))

        has_cookie_file = bool(self.cookies_file and os.path.isfile(self.cookies_file))
        if has_cookie_file:
            auth_configs.append((
                "cookies_file",
                self._base_opts(
                    out_template,
                    use_auth=True,
                    cookies_file=self.cookies_file,
                ),
            ))

        if self.cookies_browser and not has_cookie_file:
            auth_configs.append((
                f"cookies_browser={self.cookies_browser}",
                self._base_opts(
                    out_template,
                    use_auth=True,
                    cookies_browser=self.cookies_browser,
                ),
            ))

        attempts: list[tuple[str, dict]] = []
        for label, base_opts in auth_configs:
            normal = dict(base_opts)
            normal["progress_hooks"] = [_hook]
            attempts.append((label, normal))

            hls = self._hls_fallback_opts(base_opts)
            hls["progress_hooks"] = [_hook]
            attempts.append((f"{label}+web_safari_hls", hls))

        last_error = ""
        for index, (label, opts) in enumerate(attempts):
            if index:
                # Evita que um arquivo parcial de uma tentativa 403/416
                # contamine a estratégia seguinte.
                self._clean_job_files(output_path, base_name)

            print(f"[video_downloader] Tentando download de vídeo ({label})...")
            err = self._try_download(url, opts)
            if err is None and os.path.exists(final_video):
                print(f"[video_downloader] Vídeo baixado via {label}")
                return f"videos/{base_name}.mp4"

            last_error = err or "arquivo não encontrado"
            print(f"[video_downloader] Falhou ({label}): {str(last_error)[:240]}")

        from tools.yt_error_classifier import classify_download_error
        return classify_download_error(last_error)

    async def _arun(self, url: str) -> str:
        return self._run(url)
