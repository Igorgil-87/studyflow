"""
tools/instagram_client.py — publica carrossel (ou imagem única) no
Instagram via Graph API (Meta).

Fluxo confirmado na documentação oficial (developers.facebook.com/docs/
instagram-platform/content-publishing/) em 22/07/2026:
  1. Um container por imagem: POST /{ig-user-id}/media
     com image_url + is_carousel_item=true (só p/ carrossel)
  2. Container "pai": POST /{ig-user-id}/media
     com media_type=CAROUSEL + children=<id1>,<id2>,...
  3. Publicar: POST /{ig-user-id}/media_publish com creation_id=<id do pai>

Requisitos do LADO DA CONTA (não é código, é configuração manual sua),
confirmados em teste real em 24/07/2026 (fluxo "Instagram Business Login"):
  - Instagram Business ou Creator (não pessoal) — NÃO precisa estar
    vinculada a uma Página do Facebook nesse fluxo
  - App de desenvolvedor criado em developers.facebook.com, caso de uso
    "Gerenciar mensagens e conteúdo no Instagram"
  - Conta adicionada como "Testador do Instagram" na aba Funções do app
    (e convite aceito do lado do Instagram)
  - Token gerado em Configuração da API com login do Instagram > passo 2
    (token IGAA..., NÃO o EAA... do login via Facebook)
  - Permissões: instagram_business_basic, instagram_business_content_publish
    (+ manage_comments/manage_messages se for usar essas partes também)
  - Token dura ~60 dias; renovar com GET https://graph.instagram.com/
    refresh_access_token?grant_type=ig_refresh_token&access_token=...
    (token precisa ter pelo menos 24h de vida pra esse endpoint aceitar)

Credenciais (.env):
    IG_BUSINESS_ACCOUNT_ID   (o ID numérico da conta, não o @usuário)
    IG_ACCESS_TOKEN

Limite da própria Instagram: carrossel aceita até 10 imagens; a primeira
imagem define a proporção de corte das demais.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import requests
from dotenv import set_key

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
_TOKEN_ERROR_CODES = {190, 452}
_TOKEN_ERROR_SUBCODES = {2207055, 460}

GRAPH_API_VERSION = "v25.0"
# graph.instagram.com (não graph.facebook.com) — confirmado em teste real
# em 24/07/2026: o app usa o fluxo "Instagram Business Login" (token
# IGAA...), que fala com esse host. graph.facebook.com é do fluxo antigo
# (login via Facebook, token EAA...) e rejeita esse token com erro de
# sessão inválida.
GRAPH_API_BASE = f"https://graph.instagram.com/{GRAPH_API_VERSION}"

_TIMEOUT = 30


class InstagramPublishError(RuntimeError):
    """Erro ao publicar no Instagram."""


def _configured() -> bool:
    return bool(os.getenv("IG_BUSINESS_ACCOUNT_ID") and os.getenv("IG_ACCESS_TOKEN"))


def is_alive() -> bool:
    """Confirma que as credenciais existem (não há endpoint de ping)."""
    return _configured()


def _account_id() -> str:
    return os.getenv("IG_BUSINESS_ACCOUNT_ID", "")


def _token() -> str:
    return os.getenv("IG_ACCESS_TOKEN", "")


def _refresh_token() -> str:
    """Renova o token via ig_refresh_token e salva o novo no .env.
    Requer que o token atual tenha pelo menos 24h de vida e ainda esteja
    válido — se ele já expirou de vez, isso também falha (nesse caso só
    resta gerar um novo manualmente no dashboard da Meta)."""
    resp = requests.get(
        f"{GRAPH_API_BASE}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": _token()},
        timeout=_TIMEOUT,
    )
    data = resp.json()
    if resp.status_code != 200 or "access_token" not in data:
        raise InstagramPublishError(
            f"Token do Instagram expirado e não foi possível renovar automaticamente "
            f"— gere um novo manualmente no dashboard da Meta. Detalhe: {str(data)[:300]}"
        )
    new_token = data["access_token"]
    set_key(str(_ENV_PATH), "IG_ACCESS_TOKEN", new_token)
    os.environ["IG_ACCESS_TOKEN"] = new_token
    return new_token


def _is_token_error(data: dict) -> bool:
    err = data.get("error", {})
    return err.get("code") in _TOKEN_ERROR_CODES or err.get("error_subcode") in _TOKEN_ERROR_SUBCODES


def _post_with_retry(url: str, payload: dict) -> dict:
    """POST com renovação automática de token em caso de sessão inválida/expirada."""
    for attempt in range(2):
        payload["access_token"] = _token()
        try:
            r = requests.post(url, data=payload, timeout=_TIMEOUT)
        except requests.RequestException as exc:
            raise InstagramPublishError(f"Falha de rede ao chamar Instagram: {exc}") from exc

        data = r.json() if r.content else {}
        if r.status_code == 200:
            return data
        if attempt == 0 and _is_token_error(data):
            _refresh_token()
            continue
        raise InstagramPublishError(f"Erro da API do Instagram: {str(data)[:300]}")
    raise InstagramPublishError("Falha ao publicar mesmo após renovar o token.")


def _create_container(image_url: str, *, is_carousel_item: bool = False,
                       is_ai_generated: bool = False) -> str:
    """Cria um container de mídia para 1 imagem. Retorna o container ID."""
    payload = {"image_url": image_url}
    if is_carousel_item:
        payload["is_carousel_item"] = "true"
    if is_ai_generated:
        # rótulo de transparência da própria Meta pra conteúdo gerado por
        # IA — não é opcional pra "esconder", é a forma correta de marcar.
        payload["is_ai_generated"] = "true"
    data = _post_with_retry(f"{GRAPH_API_BASE}/{_account_id()}/media", payload)
    if "id" not in data:
        raise InstagramPublishError(f"Resposta sem ID de container: {str(data)[:300]}")
    return data["id"]


def _create_carousel_container(child_ids: list[str], caption: str) -> str:
    """Cria o container "pai" do carrossel, referenciando os filhos.
    is_ai_generated vai só no container pai (a doc oficial avisa: colocar
    nos filhos também dá erro)."""
    payload = {
        "media_type": "CAROUSEL",
        "children": ",".join(child_ids),
        "caption": caption,
        "is_ai_generated": "true",
    }
    data = _post_with_retry(f"{GRAPH_API_BASE}/{_account_id()}/media", payload)
    if "id" not in data:
        raise InstagramPublishError(f"Resposta sem ID do carrossel: {str(data)[:300]}")
    return data["id"]


def _publish(creation_id: str) -> str:
    """Publica o container (imagem única ou carrossel). Retorna o media ID publicado."""
    payload = {"creation_id": creation_id}
    data = _post_with_retry(f"{GRAPH_API_BASE}/{_account_id()}/media_publish", payload)
    if "id" not in data:
        raise InstagramPublishError(f"Resposta sem ID de publicação: {str(data)[:300]}")
    return data["id"]


def publish_carousel(image_urls: list[str], caption: str = "") -> str:
    """Publica um carrossel (2 a 10 imagens) ou uma imagem única (1 imagem).
    image_urls precisam ser URLs PÚBLICAS (ex: do Cloudinary) — não
    funciona com localhost. Retorna o ID da publicação no Instagram."""
    if not _configured():
        raise InstagramPublishError(
            "Instagram não configurado — defina IG_BUSINESS_ACCOUNT_ID e "
            "IG_ACCESS_TOKEN no .env."
        )
    if not image_urls:
        raise InstagramPublishError("Nenhuma imagem para publicar.")
    if len(image_urls) > 10:
        raise InstagramPublishError("Carrossel aceita no máximo 10 imagens.")

    if len(image_urls) == 1:
        # imagem única: 1 container, publica direto (sem "pai" de carrossel)
        container_id = _create_container(image_urls[0], is_carousel_item=False,
                                          is_ai_generated=True)
        return _publish(container_id)

    child_ids = [_create_container(url, is_carousel_item=True) for url in image_urls]
    parent_id = _create_carousel_container(child_ids, caption)
    return _publish(parent_id)


# ── Reels (vídeo) ────────────────────────────────────────────────────────
# Fluxo diferente do de imagem: cria o container de vídeo, mas ele NÃO
# fica pronto na hora — o Instagram processa o arquivo nos servidores
# deles (30s a poucos minutos), então precisa checar o status até dar
# "FINISHED" antes de publicar. Confirmado na documentação oficial em
# 30/07/2026 (developers.facebook.com/docs/instagram-platform/content-publishing).
_REEL_POLL_INTERVAL = 5      # segundos entre checagens de status
_REEL_POLL_MAX_TRIES = 36    # 36 x 5s = até 3min de espera


def _create_reel_container(video_url: str, caption: str, *,
                            share_to_feed: bool = True,
                            cover_url: str | None = None) -> str:
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true" if share_to_feed else "false",
        "is_ai_generated": "true",
    }
    if cover_url:
        payload["cover_url"] = cover_url
    data = _post_with_retry(f"{GRAPH_API_BASE}/{_account_id()}/media", payload)
    if "id" not in data:
        raise InstagramPublishError(f"Resposta sem ID de container de Reels: {str(data)[:300]}")
    return data["id"]


def _wait_container_ready(container_id: str) -> None:
    """Espera o container de vídeo terminar de processar (status_code ==
    FINISHED) antes de publicar. Levanta erro se der ERROR ou estourar o
    tempo máximo de espera."""
    for _ in range(_REEL_POLL_MAX_TRIES):
        r = requests.get(
            f"{GRAPH_API_BASE}/{container_id}",
            params={"fields": "status_code", "access_token": _token()},
            timeout=_TIMEOUT,
        )
        data = r.json() if r.content else {}
        status = data.get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise InstagramPublishError(
                f"Instagram falhou ao processar o vídeo: {str(data)[:300]}"
            )
        time.sleep(_REEL_POLL_INTERVAL)
    raise InstagramPublishError(
        f"Vídeo não terminou de processar em {_REEL_POLL_MAX_TRIES * _REEL_POLL_INTERVAL}s "
        "— tenta de novo em alguns minutos (containers de vídeo expiram em 24h)."
    )


def publish_reel(video_url: str, caption: str = "", *,
                  share_to_feed: bool = True,
                  cover_url: str | None = None) -> str:
    """Publica um Reels (vídeo curto). video_url precisa ser URL PÚBLICA
    (ex: do Cloudinary), MP4/H.264, até 90s pra aparecer na aba Reels
    (vídeos mais longos publicam como post de vídeo comum, não Reel).
    Retorna o ID da publicação. Demora mais que imagem (espera o
    Instagram processar o vídeo antes de poder publicar)."""
    if not _configured():
        raise InstagramPublishError(
            "Instagram não configurado — defina IG_BUSINESS_ACCOUNT_ID e "
            "IG_ACCESS_TOKEN no .env."
        )
    if not video_url:
        raise InstagramPublishError("URL do vídeo é obrigatória.")

    container_id = _create_reel_container(
        video_url, caption, share_to_feed=share_to_feed, cover_url=cover_url
    )
    _wait_container_ready(container_id)
    return _publish(container_id)
