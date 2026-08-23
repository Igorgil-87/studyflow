"""
curso/tts.py — TTS compartilhado entre Fase 3 (narração de cena de vídeo)
e Fase 4 (áudio standalone "Ouvir aula" + Podcast Mode). Único ponto do
Course Engine que faz chamada de rede real pro serviço de TTS da
Microsoft (edge-tts) — todo o resto (ffmpeg) é local.

Vozes PT-BR disponíveis no edge-tts (nomes reais do serviço, não
inventados): AntonioNeural (masculina) e FranciscaNeural (feminina) são
as usadas por padrão pro Podcast Mode (2 speakers).
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

VOZ_PADRAO = "pt-BR-AntonioNeural"
VOZES_PODCAST = {"A": "pt-BR-AntonioNeural", "B": "pt-BR-FranciscaNeural"}


class TTSError(RuntimeError):
    """Erro ao gerar áudio (TTS) ou compor/concatenar arquivos de áudio."""


def _checar_ffmpeg() -> None:
    import shutil
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise TTSError("ffmpeg/ffprobe não encontrados no PATH do servidor.")


async def _narrar_async(texto: str, out_path: str, voice: str) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(texto, voice)
    await communicate.save(out_path)


def narrar_texto(texto: str, out_path: str, voice: str = VOZ_PADRAO) -> str:
    """Gera o áudio da narração via edge-tts (gratuito, sem chave de API).
    Levanta TTSError se a síntese falhar (ex: egress bloqueado pro
    domínio da Microsoft — confirme que o servidor de produção alcança
    speech.platform.bing.com antes de considerar isso validado)."""
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    try:
        asyncio.run(_narrar_async(texto, out_path, voice))
    except Exception as e:
        raise TTSError(f"Falha ao gerar narração (edge-tts): {e}") from e
    if not Path(out_path).exists() or Path(out_path).stat().st_size == 0:
        raise TTSError("edge-tts não gerou áudio (arquivo vazio).")
    return out_path


def medir_duracao_audio(path: str) -> float:
    _checar_ffmpeg()
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return float(out.stdout.strip())
    except Exception as e:
        raise TTSError(f"ffprobe falhou em '{path}': {e}") from e


def concatenar_audios(audio_paths: list[str], out_path: str) -> str:
    """Concatena trechos de áudio (mp3) em um único arquivo — usado pro
    Podcast Mode (uma fala por vez, vozes alternadas) e também serviria
    pra emendar trechos longos de 'Ouvir aula' se precisar no futuro.
    Re-encoda (não usa '-c copy') porque chamadas separadas de edge-tts
    podem ter parâmetros internos ligeiramente diferentes entre si —
    concat por stream-copy é mais frágil nesse caso do que pra vídeo."""
    if not audio_paths:
        raise TTSError("Nenhum áudio pra concatenar.")
    _checar_ffmpeg()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    lista_path = f"{out_path}.concat_list.txt"
    with open(lista_path, "w", encoding="utf-8") as f:
        for p in audio_paths:
            f.write(f"file '{Path(p).resolve()}'\n")

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista_path,
           "-c:a", "libmp3lame", "-b:a", "160k", out_path]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=True)
    except subprocess.CalledProcessError as e:
        raise TTSError(f"ffmpeg falhou ao concatenar áudio: {e.stderr[-500:]}") from e
    finally:
        Path(lista_path).unlink(missing_ok=True)
    return out_path
