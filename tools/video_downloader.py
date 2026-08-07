"""
tools/video_downloader.py
Baixa o vídeo (.mp4) do YouTube para tocar localmente na interface.
Reaproveita as mesmas estratégias de fallback do audio_extractor
(player_client android, cookies do navegador, modo padrão).
"""

import os
from pathlib import Path
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import yt_dlp


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

    def _base_opts(self, out_template: str) -> dict:
        return {
            # limita a 720p para o arquivo não ficar gigante
            "format": "best[ext=mp4][height<=720]/best[ext=mp4]/best",
            "outtmpl": out_template,
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
            # "continuedl": False força baixar do zero sempre, em vez de
            # tentar "continuar" um download parcial de uma tentativa
            # anterior — é isso que causava HTTP 416 (Requested Range Not
            # Satisfiable): as URLs de streaming do YouTube expiram rápido,
            # então o intervalo de bytes de uma tentativa antiga já não é
            # mais válido na hora de retomar. Sem isso, o download de
            # VÍDEO ficava falhando sempre (mesmo o de ÁUDIO, que usa
            # lógica separada, continuava funcionando — por isso a
            # transcrição/IA funcionavam mas o corte do vídeo, não).
            "continuedl": False,
            "nopart": True,
            # socket_timeout: sem isso, se a conexão TRAVAR (não falhar,
            # só ficar sem responder), o yt-dlp espera pra sempre — parece
            # "looping infinito" mas na real é uma leitura de rede que
            # nunca recebe resposta nem erro. Com o timeout, isso vira um
            # erro de verdade depois de 30s, que o classify_download_error
            # consegue explicar, em vez de travar o job pro sempre.
            "socket_timeout": 30,
            # limite explícito de tentativas — o padrão do yt-dlp já é
            # finito (10), mas deixamos explícito e mais baixo aqui: se
            # vai falhar, é melhor falhar rápido e cair pro próximo dos 3
            # métodos de download, em vez de gastar minutos tentando de
            # novo o mesmo método que já não está funcionando.
            "retries": 3,
            "fragment_retries": 3,
        }

    def _try_download(self, url: str, opts: dict) -> str | None:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            return None
        except Exception as e:
            return str(e)

    def _run(self, url: str, progress_callback=None, job_id: str | None = None) -> str:
        import glob
        import time

        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # nome único por job (job_id) quando disponível — antes era um
        # nome FIXO ("current_video.mp4") compartilhado entre TODOS os
        # jobs. Isso significava que qualquer resquício deixado por um
        # job que falhou podia, em teoria, interferir no próximo job que
        # rodasse (mesmo nome de arquivo = mesmo "slot"). Com nome único,
        # cada job tem seu próprio arquivo, sem chance de um afetar o
        # outro. Sem job_id (chamada fora do pipeline), cai no nome fixo
        # de antes — mantém compatibilidade com qualquer outro uso.
        base_name = f"current_video_{job_id}" if job_id else "current_video"
        out_template = str(output_path / f"{base_name}.%(ext)s")
        final_video = str(output_path / f"{base_name}.mp4")

        # limpa QUALQUER resquício de tentativa anterior DESSE MESMO job
        # (não só o .mp4 final) — inclui .part, .ytdl, fragmentos .f###
        # etc. Deixar isso pra trás é o que fazia o yt-dlp tentar
        # "continuar" um download velho e tomar HTTP 416 do YouTube.
        for leftover in glob.glob(str(output_path / f"{base_name}.*")):
            try:
                os.remove(leftover)
            except OSError:
                pass

        # Progresso real de download (%, velocidade, ETA) — antes disso a
        # tela ficava com a mesma mensagem estática o tempo todo durante
        # um download longo (vídeo de horas = minutos de download), o que
        # parecia "travado" mesmo funcionando normal. yt-dlp chama esse
        # hook várias vezes por segundo — throttla pra 1x/2s, senão inunda
        # o SSE com evento demais.
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

        attempts = []
        opts_a = self._base_opts(out_template)
        opts_a["extractor_args"] = {"youtube": {"player_client": ["android", "web"]}}
        opts_a["progress_hooks"] = [_hook]
        attempts.append(("player_client=android", opts_a))

        if self.cookies_browser:
            opts_b = self._base_opts(out_template)
            opts_b["cookiesfrombrowser"] = (self.cookies_browser,)
            opts_b["progress_hooks"] = [_hook]
            attempts.append((f"cookies={self.cookies_browser}", opts_b))

        opts_c = self._base_opts(out_template)
        opts_c["progress_hooks"] = [_hook]
        attempts.append(("padrão", opts_c))

        last_error = ""
        for label, opts in attempts:
            print(f"[video_downloader] Tentando download de vídeo ({label})...")
            err = self._try_download(url, opts)
            if err is None and os.path.exists(final_video):
                print(f"[video_downloader] Vídeo baixado via {label}")
                # retorna o caminho relativo a /static para o front montar a URL
                return f"videos/{base_name}.mp4"
            last_error = err or "arquivo não encontrado"
            print(f"[video_downloader] Falhou ({label}): {str(last_error)[:120]}")

        from tools.yt_error_classifier import classify_download_error
        return classify_download_error(last_error)

    async def _arun(self, url: str) -> str:
        return self._run(url)
