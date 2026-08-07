"""
tools/video_splitter.py
Corta um vídeo .mp4 em clips separados por aula usando moviepy.
"""

import json
import re
import unicodedata
from pathlib import Path
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from moviepy.editor import VideoFileClip


class VideoSplitterInput(BaseModel):
    video_path: str = Field(
        description="Caminho para o arquivo de vídeo .mp4"
    )
    aulas_json: str = Field(
        description=(
            "JSON com as aulas: lista de "
            "{titulo, inicio, fim, resumo}"
        )
    )
    output_dir: str = Field(
        default="static/videos/clips",
        description="Diretório para salvar os clips gerados"
    )


class VideoSplitterTool(BaseTool):
    name: str = "video_splitter"
    description: str = (
        "Corta um vídeo em clips separados por aula. "
        "Retorna JSON com a lista de clips gerados (titulo, arquivo, "
        "duracao, resumo). Use após identificar os blocos de aulas."
    )
    args_schema: type[BaseModel] = VideoSplitterInput

    def _run(
        self,
        video_path: str,
        aulas_json: str,
        output_dir: str = "static/videos/clips",
        progress_callback=None,
    ) -> str:
        if not Path(video_path).exists():
            return f"ERRO: vídeo não encontrado: {video_path}"

        try:
            raw = json.loads(aulas_json)
            aulas = raw.get("aulas", raw) if isinstance(raw, dict) else raw
        except Exception as e:
            return f"ERRO ao parsear JSON de aulas: {e}"

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        try:
            # confirma que o vídeo abre e pega a duração total, só pra
            # validar/calcular os limites de cada aula abaixo
            probe_clip = VideoFileClip(video_path)
            total_duration = probe_clip.duration
            probe_clip.close()
        except Exception as e:
            return f"ERRO ao abrir vídeo: {e}"

        clips_result = []
        for i, aula in enumerate(aulas, 1):
            titulo = aula.get("titulo", f"Aula {i}")
            inicio = float(aula.get("inicio", 0))
            fim = min(float(aula.get("fim", total_duration)), total_duration)
            resumo = aula.get("resumo", "")

            # Normaliza para ASCII puro (remove acentos) evitando
            # problemas de URL e sistema de arquivos
            normalized = unicodedata.normalize("NFKD", titulo)
            ascii_title = normalized.encode("ascii", "ignore").decode()
            safe = re.sub(r"[^\w\s-]", "", ascii_title).strip()
            safe = safe.replace(" ", "_")[:40]
            filename = f"aula_{i:02d}_{safe}.mp4"
            clip_path = str(out_path / filename)
            # Deriva o caminho relativo a /static a partir do output_dir
            rel_dir = output_dir
            if rel_dir.startswith("static/"):
                rel_dir = rel_dir[len("static/"):]
            clip_rel = f"{rel_dir}/{filename}"

            # Clip muito curto (< 5s) gera erro no ffmpeg — pula
            if fim - inicio < 5:
                print(
                    f"[video_splitter] Clip '{titulo}' < 5s, ignorado."
                )
                continue

            try:
                print(
                    f"[video_splitter] Cortando '{titulo}' "
                    f"({inicio:.0f}s → {fim:.0f}s)..."
                )
                # progresso real pro usuário — antes disso a tela ficava
                # sem nenhuma atualização durante TODO o corte (podia
                # levar minutos em vídeo longo com vários clips), parecendo
                # travado mesmo funcionando normal. Mesma lógica do
                # progresso de download.
                if progress_callback:
                    progress_callback(f"{i}/{len(aulas)}: cortando '{titulo}'...")

                # Reabre o vídeo do ZERO pra cada clip — reaproveitar o
                # mesmo VideoFileClip pra vários .subclip()+write_videofile()
                # seguidos quebra a partir do segundo clip ('NoneType' object
                # has no attribute 'stdout', erro interno do leitor de
                # áudio do moviepy). Confirmado com teste: o mesmo corte
                # funciona reabrindo, e falha reaproveitando. Custa um
                # pouco mais (reabre/reprobe o arquivo a cada clip), mas é
                # o preço de não ter clip nenhum falhando silenciosamente
                # no meio do lote.
                video = VideoFileClip(video_path)
                clip = video.subclip(inicio, fim)
                # preset='fast' (era o padrão 'medium', mais lento) — não
                # muda a qualidade de forma perceptível pra Shorts/Reels,
                # só o tempo de encode. Mesmo raciocínio já aplicado no
                # vertical_export.py.
                clip.write_videofile(
                    clip_path,
                    codec="libx264",
                    audio_codec="aac",
                    preset="fast",
                    verbose=False,
                    logger=None,
                )
                clip.close()
                video.close()

                dur_sec = int(fim - inicio)
                dur_fmt = f"{dur_sec // 60}:{dur_sec % 60:02d}"

                clips_result.append({
                    "titulo": titulo,
                    "arquivo": clip_rel,
                    "duracao": dur_fmt,
                    "inicio": inicio,
                    "fim": fim,
                    "resumo": resumo,
                })
                print(f"[video_splitter] Salvo: {clip_path}")
                if progress_callback:
                    progress_callback(f"{i}/{len(aulas)}: '{titulo}' pronto")

            except Exception as e:
                print(f"[video_splitter] Erro em '{titulo}': {e}")
                clips_result.append({
                    "titulo": titulo,
                    "arquivo": None,
                    "duracao": "—",
                    "inicio": inicio,
                    "fim": fim,
                    "resumo": resumo,
                    "erro": str(e),
                })

        return json.dumps({"clips": clips_result}, ensure_ascii=False)

    async def _arun(self, **kwargs) -> str:
        return self._run(**kwargs)
