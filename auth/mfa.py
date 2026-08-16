"""
auth/mfa.py — verificação em duas etapas (MFA) por e-mail.

Depois do login com e-mail/senha, gera um código de 6 dígitos, envia por e-mail
e exige a confirmação. O código é guardado na sessão apenas como HASH (HMAC), com
expiração e limite de tentativas — nunca em texto.

Opcional: liga com MFA_ENABLED=1. Sem SMTP configurado, cai em modo DEV e imprime
o código no console (útil para testar o fluxo sem servidor de e-mail).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage

CODE_TTL = int(os.getenv("MFA_CODE_TTL", "600"))   # 10 minutos
MAX_ATTEMPTS = int(os.getenv("MFA_MAX_ATTEMPTS", "5"))


def is_enabled() -> bool:
    return os.getenv("MFA_ENABLED", "0") != "0"


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash(code: str, email: str) -> str:
    secret = os.getenv("SECRET_KEY", "studyflow").encode()
    return hmac.new(secret, f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


def make_challenge(email: str) -> tuple[dict, str]:
    """Cria o desafio (para guardar na sessão) e o código (para enviar)."""
    code = generate_code()
    challenge = {
        "code_hash": _hash(code, email),
        "email": email,
        "expires": time.time() + CODE_TTL,
        "attempts": 0,
    }
    return challenge, code


def verify(challenge: dict | None, code: str) -> tuple[bool, str]:
    """Retorna (ok, motivo). Não incrementa attempts — quem chama persiste."""
    if not challenge:
        return False, "Sessão expirada. Faça login novamente."
    if time.time() > challenge.get("expires", 0):
        return False, "Código expirado. Reenvie um novo."
    if challenge.get("attempts", 0) >= MAX_ATTEMPTS:
        return False, "Muitas tentativas. Reenvie um novo código."
    expected = challenge.get("code_hash", "")
    got = _hash((code or "").strip(), challenge.get("email", ""))
    if hmac.compare_digest(expected, got):
        return True, ""
    return False, "Código incorreto."


def send_code(email: str, code: str) -> bool:
    """Envia o código por SMTP. Sem SMTP, modo DEV — só imprime o código
    de verdade no console se MFA_DEV_LOG=1 estiver explicitamente ligado
    (evita vazar o código em log de produção se o SMTP cair de config
    por engano)."""
    host = os.getenv("SMTP_HOST")
    if not host:
        if os.getenv("MFA_DEV_LOG", "0") == "1":
            print(f"[mfa] SMTP não configurado — código DEV para {email}: {code}")
        else:
            print(f"[mfa] SMTP não configurado — código não enviado para {email}. "
                  "Defina MFA_DEV_LOG=1 pra ver o código no console em desenvolvimento.")
        return True
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("SMTP_USER")
        pw = os.getenv("SMTP_PASS")
        sender = os.getenv("SMTP_FROM", user or "no-reply@studyflow.local")
        msg = EmailMessage()
        msg["Subject"] = "Seu codigo StudyFlow"
        msg["From"] = sender
        msg["To"] = email
        msg.set_content(
            f"Seu codigo de verificacao StudyFlow e: {code}\n\n"
            "Ele vale por 10 minutos. Se nao foi voce, ignore este e-mail.",
            charset="utf-8",
        )
        ctx = ssl.create_default_context()
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            pass
        with smtplib.SMTP(host, port, timeout=12) as s:
            s.starttls(context=ctx)
            if user and pw:
                s.login(user, pw)
            s.send_message(msg)
        return True
    except Exception as e:
        print(f"[mfa] envio de e-mail falhou: {e}")
        return False
