"""
auth/prefs.py — preferências por usuário (chave/valor em JSON).

Usado para guardar o layout do Mission Control (ordem dos widgets, ocultos)
sem alterar a tabela de usuários. Tabela própria, fail-safe.
"""

from __future__ import annotations

import json
import os
import sqlite3

DB = os.getenv("USERS_DB", "output/users.db")


def _conn():
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    con = sqlite3.connect(DB, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute(
        "CREATE TABLE IF NOT EXISTS user_prefs ("
        "user_key TEXT, pref_key TEXT, value TEXT, "
        "PRIMARY KEY (user_key, pref_key))"
    )
    return con


def get_pref(user_key: str, pref_key: str, default=None):
    """Lê uma preferência (JSON). Retorna default se ausente ou inválida."""
    try:
        con = _conn()
        r = con.execute(
            "SELECT value FROM user_prefs WHERE user_key=? AND pref_key=?",
            (user_key, pref_key),
        ).fetchone()
        con.close()
        if not r:
            return default
        return json.loads(r["value"])
    except Exception as e:
        print(f"[prefs] leitura falhou: {e}")
        return default


def set_pref(user_key: str, pref_key: str, value) -> bool:
    """Grava uma preferência (serializa em JSON). True se ok."""
    try:
        con = _conn()
        con.execute(
            "INSERT INTO user_prefs (user_key, pref_key, value) VALUES (?,?,?) "
            "ON CONFLICT(user_key, pref_key) DO UPDATE SET value=excluded.value",
            (user_key, pref_key, json.dumps(value, ensure_ascii=False)),
        )
        con.commit()
        con.close()
        return True
    except Exception as e:
        print(f"[prefs] gravação falhou: {e}")
        return False
