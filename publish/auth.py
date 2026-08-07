"""
publish/auth.py — autenticação OAuth 2.0 com o YouTube.

Fluxo (executado UMA vez pelo usuário, no navegador dele):

    python -m publish.auth

Isso abre o navegador, você autoriza o app a enviar vídeos para o SEU canal, e
o token é salvo em YOUTUBE_TOKEN_FILE. Depois disso, o uploader reaproveita e
renova o token sozinho.

O assistente que gerou este código NÃO autentica nem publica por você — a
autorização é uma ação sua, no seu navegador, com a sua conta.
"""

from __future__ import annotations

import os

from . import config


class NotAuthenticatedError(RuntimeError):
    """Token ausente/inválido — rode `python -m publish.auth`."""


def get_credentials():
    """Carrega credenciais válidas do token salvo (renova se expirou)."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google.auth.exceptions import RefreshError

    if not os.path.exists(config.TOKEN_FILE):
        raise NotAuthenticatedError(
            f"Token não encontrado ({config.TOKEN_FILE}). "
            "Rode: python -m publish.auth"
        )

    creds = Credentials.from_authorized_user_file(config.TOKEN_FILE, config.SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                # Causa mais comum: o app OAuth no Google Cloud Console está
                # em modo "Testing" (não publicado) — nesse modo, o Google
                # EXPIRA o refresh token sozinho depois de ~7 dias, mesmo
                # sem ninguém revogar nada. Sintoma: funcionava, parou de
                # funcionar sozinho depois de alguns dias sem reautorizar.
                raise NotAuthenticatedError(
                    "Token de autorização do YouTube expirou ou foi revogado "
                    f"({e}). Rode de novo: python -m publish.auth\n"
                    "Se isso se repetir toda semana: o app OAuth no Google "
                    "Cloud Console provavelmente está em modo 'Testing' — "
                    "nesse modo o Google expira o token sozinho a cada ~7 "
                    "dias. Pra parar de expirar, publique o app OAuth "
                    "(Google Cloud Console → OAuth consent screen → Publish "
                    "App) ou adicione seu e-mail como 'test user' com prazo "
                    "maior."
                ) from e
            with open(config.TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        else:
            raise NotAuthenticatedError(
                "Credenciais inválidas. Rode novamente: python -m publish.auth"
            )
    return creds


def run_oauth_flow() -> None:
    """Fluxo interativo: abre o navegador e salva o token."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not os.path.exists(config.CLIENT_SECRETS):
        raise SystemExit(
            f"Arquivo de credenciais não encontrado: {config.CLIENT_SECRETS}\n"
            "Baixe o client_secret.json do Google Cloud Console (veja "
            "PUBLISH_YOUTUBE.md) e aponte YOUTUBE_CLIENT_SECRETS para ele."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        config.CLIENT_SECRETS, config.SCOPES
    )
    creds = flow.run_local_server(port=0)
    with open(config.TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    print(f"\n✅ Autorizado. Token salvo em {config.TOKEN_FILE}.")
    print("   Agora você pode publicar pelo botão na tela ou pela API.")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    # recarrega config após o .env
    import importlib
    importlib.reload(config)
    run_oauth_flow()
