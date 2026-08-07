"""
publish/youtube_uploader.py — envio de um corte para o YouTube.

Constrói os metadados a partir do highlight (título, descrição, hashtags) e faz
o upload resumável via YouTube Data API v3 (videos.insert).

`upload_video` aceita um `_service` injetável para testes (sem rede/credencial).
"""

from __future__ import annotations

import os

from . import config
from .auth import NotAuthenticatedError, get_credentials

# Limites da API do YouTube.
MAX_TITLE = 100
MAX_DESC = 4900
MAX_TAGS_CHARS = 480


def _clean_tag(t: str) -> str:
    return t.lstrip("#").strip().replace(",", " ")


def build_metadata(
    title: str,
    hook: str = "",
    hashtags: list[str] | None = None,
    privacy: str | None = None,
    category_id: str | None = None,
    is_short: bool = True,
) -> dict:
    """Monta o corpo (snippet + status) do videos.insert."""
    privacy = (privacy or config.PRIVACY).lower()
    if privacy not in config.VALID_PRIVACY:
        privacy = "private"

    title = (title or "Corte").strip()[:MAX_TITLE]

    hashtags = hashtags or []
    tag_line = " ".join(f"#{_clean_tag(h)}" for h in hashtags if _clean_tag(h))
    parts = []
    if hook:
        parts.append(hook.strip())
    if is_short:
        parts.append("#Shorts")
    if tag_line:
        parts.append(tag_line)
    description = "\n\n".join(parts)[:MAX_DESC]

    # tags planas (sem #), respeitando o limite de caracteres total
    tags, total = [], 0
    for h in hashtags:
        t = _clean_tag(h)
        if not t:
            continue
        if total + len(t) + 1 > MAX_TAGS_CHARS:
            break
        tags.append(t)
        total += len(t) + 1

    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id or config.CATEGORY_ID,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }


def _build_service():
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=get_credentials())


def upload_video(
    video_path: str,
    title: str,
    hook: str = "",
    hashtags: list[str] | None = None,
    privacy: str | None = None,
    category_id: str | None = None,
    _service=None,
    _media=None,
) -> dict:
    """
    Envia o vídeo e retorna {video_id, url, privacy}.
    Levanta NotAuthenticatedError se não houver token válido.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Vídeo não encontrado: {video_path}")

    body = build_metadata(title, hook, hashtags, privacy, category_id)
    service = _service or _build_service()

    media = _media
    if media is None:
        from googleapiclient.http import MediaFileUpload
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True,
                                mimetype="video/*")
    request = service.videos().insert(
        part="snippet,status", body=body, media_body=media,
    )

    response = None
    while response is None:
        _status, response = request.next_chunk()

    video_id = response.get("id") if response else None
    if not video_id:
        raise RuntimeError(f"Upload sem id de retorno: {response}")
    return {
        "video_id": video_id,
        "url": f"https://youtu.be/{video_id}",
        "privacy": body["status"]["privacyStatus"],
    }
