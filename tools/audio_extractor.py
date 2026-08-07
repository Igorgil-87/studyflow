"""
tools/audio_extractor.py
Baixa o áudio de um vídeo YouTube com yt-dlp e
opcionalmente corta os primeiros N minutos com moviepy.
"""

import os
import subprocess
from pathlib import Path
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import yt_dlp


class AudioExtractorInput(BaseModel):
    url: str = Field(description="URL completa do vídeo do YouTube")
    max_minutes: int = Field(
        default=10,
        description="Duração máxima em minutos para extrair (evita vídeos longos demais)"
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
    # navegador de onde puxar cookies (chrome, firefox, safari, edge, brave...)
    # configurado via .env / app.py. Vazio = não usa cookies.
    cookies_browser: str = ""

    def _base_opts(self, raw_audio: str) -> dict:
        return {
            "format": "bestaudio/best",
            "outtmpl": raw_audio,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }],
            # mesma blindagem do video_downloader.py contra HTTP 416
            # (Requested Range Not Satisfiable): nunca tenta "continuar"
            # um download parcial de tentativa anterior — as URLs de
            # streaming do YouTube expiram rápido, e retomar com um range
            # de bytes velho é o que causa esse erro.
            "continuedl": False,
            "nopart": True,
            # mesma blindagem contra travamento de rede do video_downloader.py
            "socket_timeout": 30,
            "retries": 3,
            "fragment_retries": 3,
        }

    def _try_download(self, url: str, opts: dict) -> str | None:
        """Tenta baixar; retorna mensagem de erro ou None se deu certo."""
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            return None
        except Exception as e:
            return str(e)

    def _run(self, url: str, max_minutes: int = 10, progress_callback=None,
             job_id: str | None = None) -> str:
        import glob
        import time

        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # nome único por job — mesmo motivo do video_downloader.py: nome
        # fixo compartilhado entre todos os jobs é um risco real de um
        # job com erro interferir no próximo. Sem job_id, cai no nome
        # fixo de antes (compatibilidade com qualquer outro uso).
        base_name = f"audio_raw_{job_id}" if job_id else "audio_raw"
        final_name = f"audio_{job_id}" if job_id else "audio"
        raw_audio = str(output_path / f"{base_name}.%(ext)s")
        final_audio = str(output_path / f"{final_name}.mp3")

        # limpa resquícios de tentativa anterior DESSE MESMO job (.part, fragmentos etc.)
        for leftover in glob.glob(str(output_path / f"{base_name}.*")):
            try:
                os.remove(leftover)
            except OSError:
                pass

        # mesmo throttle do video_downloader.py — 1 emit a cada 2s, senão
        # inunda o SSE (yt-dlp chama isso várias vezes por segundo)
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

        # ── 1. Baixa o áudio com yt-dlp (com estratégias de fallback) ──
        # YouTube bloqueia downloads automatizados ("Please sign in").
        # Tentamos, em ordem:
        #   a) player client "android" (costuma furar o bloqueio sem login)
        #   b) cookies do navegador, se configurado no .env
        #   c) modo padrão
        attempts = []

        # a) client android/ios
        opts_a = self._base_opts(raw_audio)
        opts_a["extractor_args"] = {"youtube": {"player_client": ["android", "web"]}}
        opts_a["progress_hooks"] = [_hook]
        attempts.append(("player_client=android", opts_a))

        # b) cookies do navegador
        if self.cookies_browser:
            opts_b = self._base_opts(raw_audio)
            opts_b["cookiesfrombrowser"] = (self.cookies_browser,)
            opts_b["progress_hooks"] = [_hook]
            attempts.append((f"cookies={self.cookies_browser}", opts_b))

        # c) padrão
        opts_c = self._base_opts(raw_audio)
        opts_c["progress_hooks"] = [_hook]
        attempts.append(("padrão", opts_c))

        last_error = ""
        for label, opts in attempts:
            print(f"[audio_extractor] Tentando download ({label})...")
            err = self._try_download(url, opts)
            if err is None:
                print(f"[audio_extractor] Download OK via {label}")
                break
            last_error = err
            print(f"[audio_extractor] Falhou ({label}): {err[:120]}")
        else:
            from tools.yt_error_classifier import classify_download_error
            return classify_download_error(last_error)

        raw_mp3 = str(output_path / f"{base_name}.mp3")
        if not os.path.exists(raw_mp3):
            return "ERRO: arquivo de áudio não encontrado após download."

        # ── 2. Corta com ffmpeg se necessário (muito mais rápido que moviepy) ──
        try:
            max_sec = max_minutes * 60

            # Duração real via ffprobe
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", raw_mp3],
                capture_output=True, text=True, timeout=30,
            )
            duration = float(probe.stdout.strip() or "0")

            if duration > max_sec:
                print(f"[audio_extractor] Vídeo longo ({duration/60:.1f}min). "
                      f"Cortando para {max_minutes}min com ffmpeg.")
                subprocess.run(
                    ["ffmpeg", "-y", "-i", raw_mp3, "-t", str(max_sec),
                     "-acodec", "copy", final_audio],
                    check=True, capture_output=True, timeout=120,
                )
                os.remove(raw_mp3)
            else:
                os.rename(raw_mp3, final_audio)

        except Exception as e:
            return f"ERRO ao processar áudio com ffmpeg: {e}"

        return final_audio

    async def _arun(self, url: str, max_minutes: int = 10) -> str:
        return self._run(url, max_minutes)
