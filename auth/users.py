"""
auth/users.py — armazenamento de usuários (SQLite) com senha em hash.

Usuários locais (e-mail + senha) e usuários de OAuth (Google/LinkedIn/Instagram)
moram na mesma tabela. Senhas nunca são guardadas em texto — usamos o hash do
Werkzeug (PBKDF2). Sem dependências externas além do que o Flask já traz.
"""

from __future__ import annotations

import os
import sqlite3
import time

from werkzeug.security import check_password_hash, generate_password_hash

DB = os.getenv("USERS_DB", "output/users.db")


def _conn():
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    con = sqlite3.connect(DB, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "email TEXT UNIQUE, password_hash TEXT, name TEXT, "
        "provider TEXT DEFAULT 'local', provider_id TEXT, created_at REAL)"
    )
    return con


def init() -> None:
    _conn().close()


def _row(r) -> dict | None:
    return dict(r) if r else None


def get_by_email(email: str) -> dict | None:
    if not email:
        return None
    con = _conn()
    r = con.execute("SELECT * FROM users WHERE email=?",
                    (email.strip().lower(),)).fetchone()
    con.close()
    return _row(r)


def get_by_provider(provider: str, provider_id: str) -> dict | None:
    con = _conn()
    r = con.execute("SELECT * FROM users WHERE provider=? AND provider_id=?",
                    (provider, str(provider_id))).fetchone()
    con.close()
    return _row(r)


def create_local_user(email: str, password: str, name: str | None = None) -> dict:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("E-mail inválido.")
    if not password or len(password) < 6:
        raise ValueError("A senha precisa ter ao menos 6 caracteres.")
    if get_by_email(email):
        raise ValueError("Este e-mail já está cadastrado.")
    con = _conn()
    con.execute(
        "INSERT INTO users (email, password_hash, name, provider, created_at) "
        "VALUES (?,?,?,?,?)",
        (email, generate_password_hash(password), name or email.split("@")[0],
         "local", time.time()),
    )
    con.commit()
    con.close()
    return get_by_email(email)


def verify_login(email: str, password: str) -> dict | None:
    u = get_by_email((email or "").strip().lower())
    if not u or not u.get("password_hash"):
        return None
    if check_password_hash(u["password_hash"], password or ""):
        return u
    return None


def change_password(email: str, senha_atual: str, senha_nova: str) -> None:
    """Troca a senha de um usuário local (cadastrado com e-mail/senha).
    Levanta ValueError com mensagem amigável se algo estiver errado —
    conta não encontrada, senha atual errada, ou senha nova fraca."""
    email = (email or "").strip().lower()
    user = get_by_email(email)
    if not user or not user.get("password_hash"):
        raise ValueError(
            "Essa conta não tem senha própria cadastrada aqui (pode ser "
            "login administrativo do .env ou conta OAuth) — não dá pra trocar "
            "a senha por essa tela."
        )
    if not check_password_hash(user["password_hash"], senha_atual or ""):
        raise ValueError("Senha atual incorreta.")
    if not senha_nova or len(senha_nova) < 6:
        raise ValueError("A senha nova precisa ter ao menos 6 caracteres.")
    con = _conn()
    con.execute(
        "UPDATE users SET password_hash = ? WHERE email = ?",
        (generate_password_hash(senha_nova), email),
    )
    con.commit()
    con.close()


def upsert_oauth_user(provider: str, provider_id: str,
                      email: str | None, name: str | None) -> dict:
    """Cria ou recupera o usuário vindo de um provedor OAuth."""
    existing = get_by_provider(provider, provider_id)
    if existing:
        return existing
    # tenta vincular por e-mail, se o provedor forneceu um
    if email:
        by_email = get_by_email(email)
        if by_email:
            return by_email
    con = _conn()
    con.execute(
        "INSERT INTO users (email, name, provider, provider_id, created_at) "
        "VALUES (?,?,?,?,?)",
        ((email or "").strip().lower() or None, name or "Usuário",
         provider, str(provider_id), time.time()),
    )
    con.commit()
    con.close()
    return get_by_provider(provider, provider_id)
