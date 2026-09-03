"""
tools/video_downloader.py
Baixa o vídeo do YouTube para reprodução local no módulo Curso.

Objetivos deste downloader:
- funcionar em Docker/headless sem tentar ler banco de cookies do Chrome local;
- tentar primeiro um MP4 progressivo simples;
- ter fallback para streams separados (vídeo + áudio), que é o formato mais comum
  no YouTube atual;
- garantir que o resultado final seja SEMPRE um .mp4 real em /static/videos;
- nunca retornar sucesso apenas porque o yt-dlp terminou: valida arquivo e tamanho.
"""

from __future__ import annotations

import glob
import os
import subprocess
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
        "Retorna o caminho relativo a /static."
    )
    args_schema: type[BaseModel] = VideoDownloaderInput
    output_dir: str = "static/videos"
    cookies_browser: str = ""
    cookies_file: str = ""

    @staticmethod
    def _inside_container() -> bool:
        return (
            os.path.exists("/.dockerenv")
            or os.getenv("RUNNING_IN_DOCKER", "").lower() in {"1", "true", "yes"}
            or os.getenv("CONTAINER", "").lower() in {"1", "true", "yes"}
        )

    def _base_opts(
        self,
        out_template: str,
        *,
        fmt: str,
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
            "format": fmt,
            "outtmpl": out_template,
            "merge_output_format": "mp4",
            "continuedl": False,
            "nopart": True,
            "overwrites": True,
            # Prefere H.264/AAC quando disponível porque toca nativamente em
            # Safari/Chrome e evita MP4 com codec que o browser não decodifica.
            "format_sort": ["codec:h264", "res:720", "ext:mp4:m4a"],
        })
        return opts

    def _try_download(self, url: str, opts: dict) -> str | None:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            return None
        except Exception as e:
            return str(e)

    @staticmethod
    def _valid_file(path: str) -> bool:
        try:
            return os.path.isfile(path) and os.path.getsize(path) > 1024
        except OSError:
            return False

    def _cleanup_job_files(self, output_path: Path, base_name: str) -> None:
        for leftover in glob.glob(str(output_path / f"{base_name}.*")):
            try:
                os.remove(leftover)
            except OSError:
                pass

    def _normalize_to_mp4(self, output_path: Path, base_name: str, final_video: str) -> bool:
        """Localiza o arquivo produzido e garante um MP4 reproduzível pelo browser."""
        if self._valid_file(final_video):
            return True

        candidates = []
        for path in glob.glob(str(output_path / f"{base_name}.*")):
            if path.endswith((".part", ".ytdl", ".json")):
                continue
            if self._valid_file(path):
                candidates.append(path)

        if not candidates:
            return False

        # Escolhe o maior artefato final, normalmente o vídeo já mesclado.
        source = max(candidates, key=lambda p: os.path.getsize(p))
        if source == final_video:
            return True

        # Se já for mp4 com outro nome, basta mover.
        if source.lower().endswith(".mp4"):
            os.replace(source, final_video)
            return self._valid_file(final_video)

        # WebM/MKV etc: remuxa/transcodifica apenas quando necessário.
        # Primeiro tenta stream-copy (rápido). Se o codec não couber em MP4,
        # converte para H.264 + AAC, que funciona nos browsers suportados.
        commands = [
            ["ffmpeg", "-y", "-i", source, "-c", "copy", "-movflags", "+faststart", final_video],
            [
                "ffmpeg", "-y", "-i", source,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                final_video,
            ],
        ]
        for cmd in commands:
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=900)
                if self._valid_file(final_video):
                    return True
            except Exception:
                try:
                    if os.path.exists(final_video):
                        os.remove(final_video)
                except OSError:
                    pass
        return False

    def _run(self, url: str, progress_callback=None, job_id: str | None = None) -> str:
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        base_name = f"current_video_{job_id}" if job_id else "current_video"
        out_template = str(output_path / f"{base_name}.%(ext)s")
        final_video = str(output_path / f"{base_name}.mp4")

        self._cleanup_job_files(output_path, base_name)

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

        # 1) Progressive MP4: rápido e sem merge quando disponível.
        # 2) Streams separados: padrão atual do YouTube para 720p+.
        formats = [
            "best[ext=mp4][height<=720][vcodec^=avc1][acodec!=none]/best[ext=mp4][height<=720][acodec!=none]",
            "bestvideo[height<=720][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]",
        ]

        auth_variants: list[tuple[str, dict]] = [("sem_cookies", {})]
        if self.cookies_file and os.path.isfile(self.cookies_file):
            auth_variants.append(("cookies_file", {"use_auth": True, "cookies_file": self.cookies_file}))

        # cookiesfrombrowser só é válido se o navegador existir NA MESMA máquina.
        # Dentro do Docker, COOKIES_BROWSER=chrome apontaria para /root/.config e
        # causaria o erro observado pelo usuário.
        if self.cookies_browser and not self._inside_container():
            auth_variants.append((
                f"cookies_browser={self.cookies_browser}",
                {"use_auth": True, "cookies_browser": self.cookies_browser},
            ))

        last_error = ""
        for auth_label, auth_kwargs in auth_variants:
            for format_index, fmt in enumerate(formats, start=1):
                # Limpa artefatos parciais da tentativa anterior, mas preserva
                # nada: cada tentativa deve começar do zero para não tomar 416.
                self._cleanup_job_files(output_path, base_name)
                opts = self._base_opts(out_template, fmt=fmt, **auth_kwargs)
                opts["progress_hooks"] = [_hook]
                label = f"{auth_label}/formato_{format_index}"
                print(f"[video_downloader] Tentando download de vídeo ({label})...")
                err = self._try_download(url, opts)

                if err is None and self._normalize_to_mp4(output_path, base_name, final_video):
                    print(f"[video_downloader] Vídeo pronto via {label}: {final_video}")
                    return f"videos/{base_name}.mp4"

                last_error = err or "yt-dlp terminou, mas nenhum vídeo final válido foi produzido"
                print(f"[video_downloader] Falhou ({label}): {str(last_error)[:180]}")

        from tools.yt_error_classifier import classify_download_error
        return classify_download_error(last_error)

    async def _arun(self, url: str) -> str:
        return self._run(url)
