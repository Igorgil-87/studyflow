"""
tools/video_downloader.py
Baixa vídeo do YouTube para reprodução local e geração de cortes.

Produção 2026:
- proxy residencial via PROXY_URL para evitar bloqueio de IP de datacenter;
- cookies.txt via COOKIES_FILE para autenticação headless;
- Deno/EJS para JavaScript challenges;
- PO Token Provider (BgUtils) para GVS/HTTP 403;
- estratégia progressive-first: prioriza formato 18 (MP4 com áudio+vídeo),
  comprovadamente baixável no ambiente Hetzner + Decodo + mweb + POT;
- DASH fica apenas como último fallback de seleção de formato.
"""

import glob
import os
import time
from pathlib import Path

import yt_dlp
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from tools.youtube_runtime import common_ydl_opts


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

    # O formato 18 é progressivo (vídeo+áudio no mesmo MP4) e, no ambiente
    # de produção atual, evita o 403 observado em formatos DASH separados.
    # Se ele não existir, tentamos outro progressivo antes de cair em DASH.
    VIDEO_FORMAT = (
        "18/"
        "b[ext=mp4][vcodec!=none][acodec!=none][height<=720]/"
        "b[vcodec!=none][acodec!=none][height<=720]/"
        "bv*[height<=720][ext=mp4]+ba[ext=m4a]/"
        "bestvideo[height<=720]+bestaudio/"
        "best"
    )

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
            "format": self.VIDEO_FORMAT,
            "outtmpl": out_template,
            "merge_output_format": "mp4",
            "continuedl": False,
            "nopart": True,
        })
        return opts

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

        # Ordem deliberada:
        # 1) público sem cookie; 2) cookies.txt; 3) browser apenas em dev.
        # O formato progressivo é usado em todas as variantes.
        auth_configs: list[tuple[str, dict]] = []
        auth_configs.append((
            "sem_cookies+progressive_first",
            self._base_opts(out_template, use_auth=False),
        ))

        has_cookie_file = bool(self.cookies_file and os.path.isfile(self.cookies_file))
        if has_cookie_file:
            auth_configs.append((
                "cookies_file+progressive_first",
                self._base_opts(
                    out_template,
                    use_auth=True,
                    cookies_file=self.cookies_file,
                ),
            ))

        if self.cookies_browser and not has_cookie_file:
            auth_configs.append((
                f"cookies_browser={self.cookies_browser}+progressive_first",
                self._base_opts(
                    out_template,
                    use_auth=True,
                    cookies_browser=self.cookies_browser,
                ),
            ))

        last_error = ""
        for index, (label, opts) in enumerate(auth_configs):
            if index:
                # Evita que arquivo parcial de 403/416 contamine a tentativa seguinte.
                self._clean_job_files(output_path, base_name)

            opts = dict(opts)
            opts["progress_hooks"] = [_hook]
            print(f"[video_downloader] Tentando download de vídeo ({label})...")
            err = self._try_download(url, opts)

            # yt-dlp pode terminar com extensão diferente antes do merge; o
            # merge_output_format garante MP4 quando há DASH. Para progressivo
            # 18 o arquivo já nasce MP4.
            if err is None and os.path.exists(final_video):
                print(f"[video_downloader] Vídeo baixado via {label}")
                return f"videos/{base_name}.mp4"

            last_error = err or "arquivo não encontrado"
            print(f"[video_downloader] Falhou ({label}): {str(last_error)[:240]}")

        from tools.yt_error_classifier import classify_download_error
        return classify_download_error(last_error)

    async def _arun(self, url: str) -> str:
        return self._run(url)
