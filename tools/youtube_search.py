"""
tools/youtube_search.py
Busca vídeos no YouTube e retorna os mais relevantes.
Usa yt-dlp em modo extractor (sem download) para evitar APIs pagas.
"""

import json
import yt_dlp
from tools.youtube_runtime import common_ydl_opts
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class YouTubeSearchInput(BaseModel):
    query: str = Field(description="Tema ou assunto a buscar no YouTube")
    max_results: int = Field(default=3, description="Número máximo de resultados")
    suffix: str = Field(default="tutorial",
                        description="Sufixo adicionado à busca (ex.: 'tutorial'; vazio = busca crua)")


class YouTubeSearchTool(BaseTool):
    name: str = "youtube_search"
    description: str = (
        "Busca vídeos educacionais no YouTube sobre um tema. "
        "Retorna título, URL, duração e descrição dos vídeos encontrados. "
        "Use quando o usuário quiser estudar um assunto."
    )
    args_schema: type[BaseModel] = YouTubeSearchInput

    def _run(self, query: str, max_results: int = 3, suffix: str = "tutorial") -> str:
        ydl_opts = common_ydl_opts(quiet=True, use_auth=False)
        ydl_opts.update({
            "extract_flat": True,          # não baixa, só extrai metadados
            "playlist_items": f"1-{max_results}",
        })

        term = f"{query} {suffix}".strip() if suffix else query.strip()
        search_url = f"ytsearch{max_results}:{term}"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_url, download=False)
                entries = info.get("entries", [])

            results = []
            for entry in entries:
                duration_sec = entry.get("duration", 0) or 0
                duration_min = round(duration_sec / 60, 1)
                video_id = entry.get("id", "")
                results.append({
                    "titulo": entry.get("title", "Sem título"),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "video_id": video_id,
                    "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg" if video_id else "",
                    "duracao_minutos": duration_min,
                    "canal": entry.get("uploader", "Desconhecido"),
                    "descricao": (entry.get("description") or "")[:200],
                })

            return json.dumps(results, ensure_ascii=False, indent=2)

        except Exception as e:
            return json.dumps({"erro": str(e)})

    async def _arun(self, query: str, max_results: int = 3, suffix: str = "tutorial") -> str:
        return self._run(query, max_results, suffix)
