"""publish/config.py — configuração da publicação no YouTube."""

import os

CLIENT_SECRETS = os.getenv("YOUTUBE_CLIENT_SECRETS", "client_secret.json")
TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", "youtube_token.json")
PRIVACY = os.getenv("YOUTUBE_PRIVACY", "private").strip().lower()
CATEGORY_ID = os.getenv("YOUTUBE_CATEGORY_ID", "22")

# Escopo mínimo necessário para enviar vídeos + ler métricas (Analytics,
# só leitura — não dá nenhum acesso de escrita além do já existente).
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

VALID_PRIVACY = {"private", "unlisted", "public"}
