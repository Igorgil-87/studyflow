"""
auth/ — autenticação do StudyFlow.

- login_required: protege rotas (sessão Flask).
- check_credentials: compat com o admin do .env + usuários locais do banco.
- users: banco de usuários (e-mail/senha + OAuth).
- oauth: login social opcional (Google/LinkedIn/Instagram).
"""

import os
from functools import wraps

from flask import redirect, session, url_for

from . import users, oauth  # noqa: F401

APP_USER = os.getenv("APP_USER", "admin")
APP_PASS = os.getenv("APP_PASS", "studyflow")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def check_credentials(username: str, password: str) -> bool:
    """Compat: admin do .env OU usuário local cadastrado (por e-mail)."""
    if username == APP_USER and password == APP_PASS:
        return True
    return users.verify_login(username, password) is not None
