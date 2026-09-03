"""
tools/audio_extractor.py
Extrai áudio para transcrição.

Estratégia de produção:
- preferir extrair o áudio do vídeo já baixado localmente, evitando uma
  segunda chamada ao YouTube, gasto duplicado de proxy e novos riscos de 403;
- manter download direto por yt-dlp como fallback para fluxos que não tenham
  vídeo local;
- quando baixar direto, priorizar formato progressivo 18 antes de DASH áudio.
"""

import glob
import os
import subprocess
import time
from pathlib import Path

import yt_dlp
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from tools.youtube_runtime import common_ydl_opts


class AudioExtractorInput(BaseModel):
    url: str = Field(description="URL completa do vídeo do YouTube")
    max_minutes: int = Field(
        default=10,
        description="Duração máxima em minutos para extrair (evita vídeos longos demais)",
    )


class AudioExtractorTool(BaseTool):
    name: str = "audio_extractor"
    description: str = (
        "Baixa ou extrai o áudio de um vídeo do YouTube e salva como .mp3. "
        "Retorna o caminho do arquivo de áudio gerado."
    )
    args_schema: type[BaseModel] = AudioExtractorInput
    output_dir: str = "output"
    cookies_browser: str = ""
    cookies_file: str = ""

    # Se precisarmos acessar o YouTube diretamente, o formato 18 é o primeiro
    # candidato porque já foi validado em produção com mweb + POT + proxy.
    AUDIO_SOURCE_FORMAT = (
        "18/"
        "b[ext=mp4][vcodec!=none][acodec!=none]/"
        "bestaudio[ext=m4a]/"
        "bestaudio/"
        "best"
    )

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
            "format": self.AUDIO_SOURCE_FORMAT,
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

    def _final_audio_path(self, job_id: str | None = None) -> str:
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        final_name = f"audio_{job_id}" if job_id else "audio"
        return str(output_path / f"{final_name}.mp3")

    def extract_from_video(
        self,
        video_path: str,
        max_minutes: int = 10,
        job_id: str | None = None,
    ) -> str:
        """Extrai MP3 de um vídeo local já baixado.

        Este é o caminho preferido em produção: uma única transferência do
        YouTube alimenta tanto os cortes quanto a transcrição.
        """
        if not video_path or not os.path.isfile(video_path):
            return f"ERRO: vídeo local não encontrado para extração de áudio: {video_path}"

        final_audio = self._final_audio_path(job_id)
        try:
            if os.path.exists(final_audio):
                os.remove(final_audio)

            max_sec = max(1, int(max_minutes)) * 60
            print(
                f"[audio_extractor] Extraindo áudio do vídeo local "
                f"(máx. {max_minutes}min)..."
            )
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", video_path,
                    "-t", str(max_sec),
                    "-vn",
                    "-ac", "2",
                    "-ar", "44100",
                    "-b:a", "128k",
                    final_audio,
                ],
                check=True,
                capture_output=True,
                timeout=max(180, max_sec + 120),
            )
        except subprocess.TimeoutExpired:
            return "ERRO ao processar áudio com ffmpeg: timeout na extração local."
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or b"").decode("utf-8", errors="replace")[-1200:]
            return f"ERRO ao processar áudio com ffmpeg: {detail or exc}"
        except Exception as exc:
            return f"ERRO ao processar áudio com ffmpeg: {exc}"

        if not os.path.isfile(final_audio) or os.path.getsize(final_audio) == 0:
            return "ERRO: ffmpeg não gerou o arquivo de áudio esperado."

        print(f"[audio_extractor] Áudio local pronto: {final_audio}")
        return final_audio

    def _run(
        self,
        url: str,
        max_minutes: int = 10,
        progress_callback=None,
        job_id: str | None = None,
    ) -> str:
        """Fallback: baixa uma fonte do YouTube e converte para MP3."""
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        base_name = f"audio_raw_{job_id}" if job_id else "audio_raw"
        raw_audio = str(output_path / f"{base_name}.%(ext)s")
        final_audio = self._final_audio_path(job_id)
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
        auth_configs.append((
            "sem_cookies+progressive_first",
            self._base_opts(raw_audio, use_auth=False),
        ))

        has_cookie_file = bool(self.cookies_file and os.path.isfile(self.cookies_file))
        if has_cookie_file:
            auth_configs.append((
                "cookies_file+progressive_first",
                self._base_opts(
                    raw_audio,
                    use_auth=True,
                    cookies_file=self.cookies_file,
                ),
            ))

        if self.cookies_browser and not has_cookie_file:
            auth_configs.append((
                f"cookies_browser={self.cookies_browser}+progressive_first",
                self._base_opts(
                    raw_audio,
                    use_auth=True,
                    cookies_browser=self.cookies_browser,
                ),
            ))

        last_error = ""
        for index, (label, opts) in enumerate(auth_configs):
            if index:
                self._clean_raw_files(output_path, base_name)

            opts = dict(opts)
            opts["progress_hooks"] = [_hook]
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
            max_sec = max(1, int(max_minutes)) * 60
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
                if os.path.exists(final_audio):
                    os.remove(final_audio)
                os.replace(raw_mp3, final_audio)

        except Exception as exc:
            return f"ERRO ao processar áudio com ffmpeg: {exc}"

        return final_audio

    async def _arun(self, url: str, max_minutes: int = 10) -> str:
        return self._run(url, max_minutes)
