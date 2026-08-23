"""
curso/audio_render.py — Fase 4 do AI Course Generation Engine (ver
ai-course-engine-diagnostico.md, seção 9).

Dois modos, ambos em cima de curso/tts.py:
  gerar_audio_aula()    -> "Ouvir aula": narração única do texto da
                            explicação, sem passar pelo vídeo (item 7 do
                            pedido: "adicionar Ouvir aula")
  gerar_podcast_aula()  -> Podcast Mode: um clipe por fala do roteiro
                            (curso/podcast_agent.py), voz alternada por
                            speaker, concatenados num único mp3
"""

from __future__ import annotations

import uuid
from pathlib import Path

from .tts import TTSError, VOZES_PODCAST, VOZ_PADRAO, concatenar_audios, narrar_texto


class AudioRenderError(RuntimeError):
    """Erro ao renderizar o áudio da aula ou do podcast."""


def gerar_audio_aula(titulo_aula: str, texto: str, out_dir: str, voice: str = VOZ_PADRAO) -> str:
    """Narração única (1 voz) do texto da aula inteiro. Retorna o
    caminho do mp3 final."""
    if not texto or len(texto.strip()) < 20:
        raise AudioRenderError("Texto da aula vazio ou curto demais pra gerar áudio.")
    out_path = str(Path(out_dir) / f"aula_{uuid.uuid4().hex[:8]}.mp3")
    try:
        return narrar_texto(texto, out_path, voice=voice)
    except TTSError as e:
        raise AudioRenderError(str(e)) from e


def gerar_podcast_aula(
    titulo_aula: str, script: dict, out_dir: str,
    vozes: dict[str, str] = VOZES_PODCAST, progress_callback=None,
) -> str:
    """script: saída de curso/podcast_agent.gerar_podcast_script()
    ({"turns": [{"speaker": "A"|"B", "text": ...}, ...]}). Gera um clipe
    de áudio por fala (voz correspondente ao speaker) e concatena tudo
    num mp3 só. progress_callback(i, total), se passado, é chamado por
    fala — pra progresso via SSE, mesmo padrão do vídeo (Fase 3)."""
    turns = script.get("turns", [])
    if not turns:
        raise AudioRenderError("Roteiro do podcast sem falas.")

    work_dir = Path(out_dir) / f"podcast_{uuid.uuid4().hex[:8]}"
    work_dir.mkdir(parents=True, exist_ok=True)

    clipes = []
    try:
        for i, fala in enumerate(turns):
            if progress_callback:
                progress_callback(i, len(turns))
            voice = vozes.get(fala["speaker"], VOZ_PADRAO)
            clipe = narrar_texto(fala["text"], str(work_dir / f"fala_{i}.mp3"), voice=voice)
            clipes.append(clipe)
    except TTSError as e:
        raise AudioRenderError(str(e)) from e

    if progress_callback:
        progress_callback(len(turns), len(turns))

    final_path = str(work_dir / "podcast_final.mp3")
    try:
        concatenar_audios(clipes, final_path)
    except TTSError as e:
        raise AudioRenderError(str(e)) from e
    return final_path
