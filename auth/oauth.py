"""
auth/oauth.py — login social (Google · LinkedIn · Instagram) via Authlib.

Cada provedor só é registrado se as credenciais existirem no ambiente, então o
app roda normalmente mesmo sem nenhum configurado (aí só vale e-mail + senha).
Authlib é importado de forma tardia: se não estiver instalado, OAuth fica off.

Variáveis de ambiente esperadas (por provedor):
  GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET
  LINKEDIN_CLIENT_ID     / LINKEDIN_CLIENT_SECRET
  INSTAGRAM_CLIENT_ID    / INSTAGRAM_CLIENT_SECRET
"""

from __future__ import annotations

import os

_oauth = None
_enabled: list[str] = []


def enabled_providers() -> list[str]:
    return list(_enabled)


def get_oauth():
    return _oauth


def init_oauth(app):
    """Registra os provedores configurados. Retorna (oauth, lista_habilitados)."""
    global _oauth, _enabled
    try:
        from authlib.integrations.flask_client import OAuth
    except ImportError:
        print("[oauth] authlib ausente — login social desligado "
              "(pip install authlib). E-mail/senha seguem funcionando.")
        return None, []

    oauth = OAuth(app)
    enabled: list[str] = []

    g_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    g_sec = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    if g_id and g_sec:
        oauth.register(
            name="google",
            client_id=g_id, client_secret=g_sec,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )
        enabled.append("google")

    li_id = os.getenv("LINKEDIN_CLIENT_ID")
    li_sec = os.getenv("LINKEDIN_CLIENT_SECRET")
    if li_id and li_sec:
        oauth.register(
            name="linkedin",
            client_id=li_id, client_secret=li_sec,
            authorize_url="https://www.linkedin.com/oauth/v2/authorization",
            access_token_url="https://www.linkedin.com/oauth/v2/accessToken",
            userinfo_endpoint="https://api.linkedin.com/v2/userinfo",
            client_kwargs={"scope": "openid profile email"},
        )
        enabled.append("linkedin")

    ig_id = os.getenv("INSTAGRAM_CLIENT_ID")
    ig_sec = os.getenv("INSTAGRAM_CLIENT_SECRET")
    if ig_id and ig_sec:
        oauth.register(
            name="instagram",
            client_id=ig_id, client_secret=ig_sec,
            authorize_url="https://api.instagram.com/oauth/authorize",
            access_token_url="https://api.instagram.com/oauth/access_token",
            client_kwargs={"scope": "user_profile", "token_endpoint_auth_method": "client_secret_post"},
        )
        enabled.append("instagram")

    _oauth, _enabled = oauth, enabled
    if enabled:
        print(f"[oauth] provedores habilitados: {', '.join(enabled)}")
    return oauth, enabled


def extract_userinfo(provider: str, oauth, token) -> dict:
    """Extrai {provider_id, email, name} do provedor após o callback."""
    if provider == "google":
        info = token.get("userinfo") or oauth.google.userinfo()
        return {"provider_id": info.get("sub"),
                "email": info.get("email"),
                "name": info.get("name") or info.get("given_name")}
    if provider == "linkedin":
        info = oauth.linkedin.userinfo(token=token)
        return {"provider_id": info.get("sub"),
                "email": info.get("email"),
                "name": info.get("name")}
    if provider == "instagram":
        # Instagram Basic Display: token traz user_id; buscamos o username.
        import urllib.request, json
        at = token.get("access_token")
        uid = token.get("user_id")
        username = None
        try:
            url = (f"https://graph.instagram.com/me?fields=id,username"
                   f"&access_token={at}")
            with urllib.request.urlopen(url, timeout=8) as r:
                data = json.loads(r.read().decode())
                username = data.get("username")
                uid = data.get("id", uid)
        except Exception as e:
            print(f"[oauth] instagram username falhou: {e}")
        return {"provider_id": uid, "email": None,
                "name": username or "Usuário Instagram"}
    return {"provider_id": None, "email": None, "name": None}
