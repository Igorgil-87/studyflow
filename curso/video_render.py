"""
curso/video_render.py — VideoRenderAgent (Fase 3 do AI Course Generation
Engine, ver ai-course-engine-diagnostico.md, seção 8).

Renderiza cada cena do storyboard (curso/storyboard_agent.py) e concatena
num vídeo final por aula. Determinístico e sem custo de IA de imagem:

  cena "diagrama" -> Pillow desenha um card (título + bullets, mesma
      identidade visual do certificado.py) + narração via edge-tts (TTS
      gratuito, sem chave de API) -> ffmpeg cola imagem+áudio num MP4
  cena "footage"  -> AINDA NÃO INTEGRADO com tools/mpt_client.py nesta
      primeira versão (exigiria o serviço MPT rodando e testável de
      verdade, fora do escopo desta rodada) — cai pro mesmo renderer de
      diagrama, com o texto da narração como conteúdo visual. Ver TODO
      abaixo antes de tratar isso como "gera vídeo de exemplo real".

Todas as chamadas de rede real (TTS) ficam isoladas em narrar_cena() —
é o único ponto que precisa da Microsoft TTS estar alcançável do
servidor; todo o resto (imagem, ffmpeg) é local e testável offline.
"""

from __future__ import annotations

import subprocess
import textwrap
import uuid
from pathlib import Path

from PIL import Image, ImageDraw

from certificado import _center_text, _font
from .tts import TTSError, VOZ_PADRAO, medir_duracao_audio, narrar_texto  # noqa: F401

W, H = 1280, 720  # 16:9 — padrão de vídeo, diferente do certificado (que é 1200x850)
BG = (14, 14, 16)
LIME = (212, 255, 79)
INK = (244, 243, 240)
INK2 = (155, 154, 150)


class VideoRenderError(RuntimeError):
    """Erro ao renderizar uma cena ou montar o vídeo final."""


def _checar_ffmpeg() -> None:
    import shutil
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise VideoRenderError("ffmpeg/ffprobe não encontrados no PATH do servidor.")


def narrar_cena(texto: str, out_path: str, voice: str = VOZ_PADRAO) -> str:
    """Alias fino sobre curso.tts.narrar_texto — mantido com este nome
    (e este módulo) por compatibilidade: gerar_video_aula() e os testes
    da Fase 3 chamam por 'narrar_cena'. A implementação real (e a única
    chamada de rede pro TTS) vive em curso/tts.py, compartilhada com a
    Fase 4 (áudio standalone + Podcast Mode)."""
    try:
        return narrar_texto(texto, out_path, voice)
    except TTSError as e:
        raise VideoRenderError(str(e)) from e


# ── Cena tipo "diagrama" (determinística, Pillow) ────────────────────────

def render_diagram_scene(visual_description: str, out_path: str) -> str:
    """visual_description: texto livre do StoryboardAgent — primeira
    linha vira título, o resto vira bullets. Determinístico: mesma
    entrada -> mesma imagem, sem chamar LLM nenhum aqui."""
    linhas = [ln.strip("-• ").strip() for ln in visual_description.splitlines() if ln.strip()]
    if len(linhas) <= 1:
        # StoryboardAgent pode mandar tudo numa linha só — separa por frase
        partes = [p.strip() for p in visual_description.replace("•", ".").split(".") if p.strip()]
        linhas = partes if partes else [visual_description]

    titulo, bullets = linhas[0], linhas[1:6]  # título + até 5 bullets

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 6], fill=LIME)  # barra de identidade no topo

    y = 140
    titulo_font = _font(46, bold=True)
    for linha in textwrap.wrap(titulo, width=32):
        _center_text(d, y, linha, titulo_font, INK, cx=W // 2)
        y += 60

    y += 30
    bullet_font = _font(28)
    for bullet in bullets:
        wrapped = textwrap.wrap(bullet, width=52) or [bullet]
        for j, linha in enumerate(wrapped):
            prefixo = "•  " if j == 0 else "   "
            d.text((160, y), prefixo + linha, font=bullet_font, fill=INK2)
            y += 42
        y += 14

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    return out_path


# ── Composição ffmpeg ─────────────────────────────────────────────────────

def montar_clipe_estatico(imagem_path: str, audio_path: str, out_path: str) -> str:
    """Imagem parada + trilha de áudio -> MP4 com duração = duração do
    áudio. Puro ffmpeg via subprocess, mesmo padrão de tools/video_concat.py."""
    _checar_ffmpeg()
    duracao = medir_duracao_audio(audio_path)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", imagem_path, "-i", audio_path,
        "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "160k",
        "-pix_fmt", "yuv420p", "-t", str(duracao), "-shortest", out_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=True)
    except subprocess.CalledProcessError as e:
        raise VideoRenderError(f"ffmpeg falhou ao montar clipe estático: {e.stderr[-500:]}") from e
    return out_path


def concatenar_clipes(clip_paths: list[str], out_path: str) -> str:
    """Concatena clipes MP4 (mesmo codec/resolução — todos vieram de
    montar_clipe_estatico, então são compatíveis) via concat demuxer do
    ffmpeg — mais rápido e confiável que re-encodar tudo de novo."""
    if not clip_paths:
        raise VideoRenderError("Nenhum clipe pra concatenar.")
    _checar_ffmpeg()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    lista_path = f"{out_path}.concat_list.txt"
    with open(lista_path, "w", encoding="utf-8") as f:
        for p in clip_paths:
            f.write(f"file '{Path(p).resolve()}'\n")

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lista_path, "-c", "copy", out_path]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=True)
    finally:
        Path(lista_path).unlink(missing_ok=True)
    return out_path


# ── Orquestração: storyboard inteiro -> vídeo final da aula ──────────────

def gerar_video_aula(
    titulo_aula: str, storyboard: dict, out_dir: str, voice: str = VOZ_PADRAO,
    progress_callback=None,
) -> str:
    """storyboard: saída de curso/storyboard_agent.gerar_storyboard()
    (dict com "scenes"). Retorna o caminho do MP4 final. progress_callback,
    se passado, é chamado com (indice_cena, total_cenas) — pra emitir
    progresso via SSE no pipeline assíncrono."""
    scenes = storyboard.get("scenes", [])
    if not scenes:
        raise VideoRenderError("Storyboard sem cenas.")

    work_dir = Path(out_dir) / f"aula_{uuid.uuid4().hex[:8]}"
    work_dir.mkdir(parents=True, exist_ok=True)

    clipes = []
    for i, cena in enumerate(scenes):
        if progress_callback:
            progress_callback(i, len(scenes))

        # cena "footage" ainda cai no renderer de diagrama nesta versão —
        # ver docstring do módulo (TODO: integrar tools/mpt_client.py)
        img_path = render_diagram_scene(cena["visual_description"], str(work_dir / f"cena_{i}.png"))
        audio_path = narrar_cena(cena["narration"], str(work_dir / f"cena_{i}.mp3"), voice=voice)
        clipe_path = montar_clipe_estatico(img_path, audio_path, str(work_dir / f"cena_{i}.mp4"))
        clipes.append(clipe_path)

    if progress_callback:
        progress_callback(len(scenes), len(scenes))

    final_path = str(work_dir / "final.mp4")
    concatenar_clipes(clipes, final_path)
    return final_path
