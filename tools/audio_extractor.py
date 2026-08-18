"""
tools/audio_extractor.py
Baixa áudio de vídeo YouTube com yt-dlp e corta a duração com ffmpeg.

Produção 2026:
- proxy residencial via PROXY_URL;
- COOKIES_FILE para servidor headless;
- Deno/EJS;
- PO Token Provider para GVS/HTTP 403;
- fallback web_safari/HLS.
"""

import glob
import os
import subprocess
import time
from pathlib import Path

import yt_dlp
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from tools.youtube_runtime import common_ydl_opts, with_youtube_client


class AudioExtractorInput(BaseModel):
    url: str = Field(description="URL completa do vídeo do YouTube")
    max_minutes: int = Field(
        default=10,
        description="Duração máxima em minutos para extrair (evita vídeos longos demais)",
    )


class AudioExtractorTool(BaseTool):
    name: str = "audio_extractor"
    description: str = (
        "Baixa o áudio de um vídeo do YouTube e o salva como .mp3. "
        "Retorna o caminho do arquivo de áudio gerado. "
        "Use após escolher o vídeo que será transcrito."
    )
    args_schema: type[BaseModel] = AudioExtractorInput
    output_dir: str = "output"
    cookies_browser: str = ""
    cookies_file: str = ""

    def _base_opts(
        self,
        raw_audio: str,
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
            "format": "bestaudio/best",
            "outtmpl": raw_audio,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }],
            "continuedl": False,
            "nopart": True,
        })
        return opts

    @staticmethod
    def _hls_fallback_opts(opts: dict) -> dict:
        fallback = with_youtube_client(opts, "web_safari")
        fallback["format"] = "bestaudio[protocol^=m3u8]/bestaudio/best"
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
    def _clean_raw_files(output_path: Path, base_name: str) -> None:
        for leftover in glob.glob(str(output_path / f"{base_name}.*")):
            try:
                os.remove(leftover)
            except OSError:
                pass

    def _run(
        self,
        url: str,
        max_minutes: int = 10,
        progress_callback=None,
        job_id: str | None = None,
    ) -> str:
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        base_name = f"audio_raw_{job_id}" if job_id else "audio_raw"
        final_name = f"audio_{job_id}" if job_id else "audio"
        raw_audio = str(output_path / f"{base_name}.%(ext)s")
        final_audio = str(output_path / f"{final_name}.mp3")
        self._clean_raw_files(output_path, base_name)

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

        auth_configs: list[tuple[str, dict]] = []
        auth_configs.append(("sem_cookies", self._base_opts(raw_audio, use_auth=False)))

        has_cookie_file = bool(self.cookies_file and os.path.isfile(self.cookies_file))
        if has_cookie_file:
            auth_configs.append((
                "cookies_file",
                self._base_opts(
                    raw_audio,
                    use_auth=True,
                    cookies_file=self.cookies_file,
                ),
            ))

        if self.cookies_browser and not has_cookie_file:
            auth_configs.append((
                f"cookies_browser={self.cookies_browser}",
                self._base_opts(
                    raw_audio,
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
                self._clean_raw_files(output_path, base_name)

            print(f"[audio_extractor] Tentando download ({label})...")
            err = self._try_download(url, opts)
            if err is None:
                print(f"[audio_extractor] Download OK via {label}")
                break

            last_error = err or "erro desconhecido"
            print(f"[audio_extractor] Falhou ({label}): {last_error[:240]}")
        else:
            from tools.yt_error_classifier import classify_download_error
            return classify_download_error(last_error)

        raw_mp3 = str(output_path / f"{base_name}.mp3")
        if not os.path.exists(raw_mp3):
            return "ERRO: arquivo de áudio não encontrado após download."

        try:
            max_sec = max_minutes * 60
            probe = subprocess.run(
                [
                    "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                    "-of", "csv=p=0", raw_mp3,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            duration = float(probe.stdout.strip() or "0")

            if duration > max_sec:
                print(
                    f"[audio_extractor] Vídeo longo ({duration / 60:.1f}min). "
                    f"Cortando para {max_minutes}min com ffmpeg."
                )
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", raw_mp3, "-t", str(max_sec),
                        "-acodec", "copy", final_audio,
                    ],
                    check=True,
                    capture_output=True,
                    timeout=120,
                )
                os.remove(raw_mp3)
            else:
                os.replace(raw_mp3, final_audio)

        except Exception as exc:
            return f"ERRO ao processar áudio com ffmpeg: {exc}"

        return final_audio

    async def _arun(self, url: str, max_minutes: int = 10) -> str:
        return self._run(url, max_minutes)
