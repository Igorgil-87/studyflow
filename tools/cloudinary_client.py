"""
tools/cloudinary_client.py — sobe imagens locais pro Cloudinary e devolve
URLs públicas em HTTPS.

Por que existir: a API de publicação do Instagram (Graph API) exige uma
URL pública pra cada imagem — os servidores da Meta baixam a imagem
sozinhos a partir dela. O StudyFlow roda local (localhost/Docker), que
o Instagram não alcança. O Cloudinary resolve isso: sobe o arquivo,
devolve uma URL pública permanente, sem precisar manter nenhum túnel
(tipo ngrok) rodando toda vez que for publicar.

Credenciais (.env):
    CLOUDINARY_CLOUD_NAME
    CLOUDINARY_API_KEY
    CLOUDINARY_API_SECRET
Conta grátis em https://cloudinary.com — sem cartão de crédito.
"""

from __future__ import annotations

import os
from pathlib import Path

import cloudinary
import cloudinary.uploader
from cloudinary.exceptions import Error as CloudinaryError


class CloudinaryUploadError(RuntimeError):
    """Erro ao subir imagem pro Cloudinary."""


def _configured() -> bool:
    return bool(
        os.getenv("CLOUDINARY_CLOUD_NAME")
        and os.getenv("CLOUDINARY_API_KEY")
        and os.getenv("CLOUDINARY_API_SECRET")
    )


def is_alive() -> bool:
    """Não há endpoint de health-check — só confirma que as 3 credenciais existem."""
    return _configured()


def upload_image(local_path: str | Path, *, folder: str = "studyflow") -> str:
    """Sobe uma imagem local e retorna a URL pública (https, permanente)."""
    if not _configured():
        raise CloudinaryUploadError(
            "Cloudinary não configurado — defina CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY e CLOUDINARY_API_SECRET no .env."
        )
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True,
    )
    try:
        result = cloudinary.uploader.upload(str(local_path), folder=folder)
    except CloudinaryError as exc:
        raise CloudinaryUploadError(f"Falha ao subir imagem pro Cloudinary: {exc}") from exc

    url = result.get("secure_url")
    if not url:
        raise CloudinaryUploadError(f"Cloudinary não retornou URL. Resposta: {str(result)[:300]}")
    return url


def upload_images(local_paths: list[str | Path], *, folder: str = "studyflow") -> list[str]:
    """Sobe várias imagens e retorna as URLs públicas na mesma ordem."""
    return [upload_image(p, folder=folder) for p in local_paths]


def upload_video(local_path: str | Path, *, folder: str = "studyflow") -> str:
    """Sobe um vídeo local e retorna a URL pública (https, permanente).
    Mesma ideia do upload_image, só que com resource_type='video' — usado
    pelo Reels do Instagram, que também exige URL pública (não aceita
    arquivo local)."""
    if not _configured():
        raise CloudinaryUploadError(
            "Cloudinary não configurado — defina CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY e CLOUDINARY_API_SECRET no .env."
        )
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True,
    )
    try:
        result = cloudinary.uploader.upload(
            str(local_path), folder=folder, resource_type="video"
        )
    except CloudinaryError as exc:
        raise CloudinaryUploadError(f"Falha ao subir vídeo pro Cloudinary: {exc}") from exc

    url = result.get("secure_url")
    if not url:
        raise CloudinaryUploadError(f"Cloudinary não retornou URL. Resposta: {str(result)[:300]}")
    return url
