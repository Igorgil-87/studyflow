"""
app.py — Backend Flask do StudyFlow (YouTube Study Agent).

Refatorado para escala horizontal. O processo web agora é fino:
recebe requisições, despacha o trabalho para a fila (infra.dispatch) e
transmite o progresso pelo barramento (infra.bus). Nenhum pipeline roda
mais dentro do request, e o estado vive fora do processo (infra.jobs).

Modo de execução por env (ver infra/config.py):
  - RUN_MODE=inline (padrão): tudo em processo, igual ao original.
  - RUN_MODE=redis: workers separados (worker.py) + SSE via Redis Pub/Sub.

Rotas (inalteradas para o frontend):
  GET/POST /login · GET /logout
  GET /curso · GET /youtuber · GET /trends
  POST /api/generate
  POST /api/youtuber/trends · POST /api/youtuber/generate
  POST /api/trends/analyze
  GET  /api/stream/<job_id>  (SSE)
  GET  /api/quiz/<job_id>
  GET  /healthz
"""

import json
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask, Response, jsonify, redirect,
    render_template, request, session, url_for,
)
from flask_cors import CORS
from flask_wtf.csrf import CSRFProtect, generate_csrf

from auth import check_credentials, login_required
from auth import users as auth_users
from auth import oauth as auth_oauth
from auth import mfa as auth_mfa
from infra import bus, config, jobs
from infra.dispatch import dispatch
from obs import db as obs_db
from obs import drift as obs_drift
from obs import report as obs_report
from tools import TrendFetcherTool, CATEGORIES as TREND_CATEGORIES

load_dotenv()

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
COOKIES_BROWSER = os.getenv("COOKIES_BROWSER", "").strip()
SECRET_KEY = os.getenv("SECRET_KEY", "studyflow-dev-secret-change-me")

app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)

# CSRF: protegido só nos formulários HTML de verdade (login/signup/MFA),
# não nas rotas de API/AJAX (essas usam sessão + login_required, e ligar
# proteção CSRF nelas sem testar caso a caso quebraria funcionalidade
# sem aviso — WTF_CSRF_CHECK_DEFAULT=False deixa a proteção "opt-in",
# só onde chamamos csrf.protect() explicitamente).
app.config["WTF_CSRF_CHECK_DEFAULT"] = False
csrf = CSRFProtect(app)
app.jinja_env.globals["csrf_token"] = generate_csrf

# Banco de usuários + provedores OAuth (só os configurados ligam).
auth_users.init()
oauth, OAUTH_PROVIDERS = auth_oauth.init_oauth(app)

# Garante o schema de observabilidade no processo web (idempotente).
obs_db.init()


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── Auth ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if session.get("logged_in"):
        return render_template("home.html", username=session.get("user", ""))
    return redirect(url_for("login"))


def _finish_login(name):
    session["logged_in"] = True
    session["user"] = name
    return redirect(url_for("index"))


def _start_mfa(user):
    """Inicia o desafio MFA: guarda na sessão e envia o código."""
    email = user.get("email")
    challenge, code = auth_mfa.make_challenge(email)
    session["mfa"] = challenge
    session["mfa_name"] = user.get("name") or email
    auth_mfa.send_code(email, code)
    return redirect(url_for("mfa_verify"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        csrf.protect()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        # Admin do .env: atalho sem e-mail, sem MFA.
        if username == os.getenv("APP_USER", "admin") and \
           password == os.getenv("APP_PASS", "studyflow"):
            return _finish_login(username)
        user = auth_users.verify_login(username, password)
        if user:
            if auth_mfa.is_enabled() and user.get("email"):
                return _start_mfa(user)
            return _finish_login(user.get("name") or username)
        return render_template("login.html", error="Usuário ou senha incorretos.",
                               providers=OAUTH_PROVIDERS)
    return render_template("login.html", providers=OAUTH_PROVIDERS)


@app.route("/signup", methods=["POST"])
def signup():
    csrf.protect()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    name = request.form.get("name", "").strip() or None
    try:
        user = auth_users.create_local_user(email, password, name)
    except ValueError as e:
        return render_template("login.html", error=str(e), mode="signup",
                               providers=OAUTH_PROVIDERS)
    if auth_mfa.is_enabled() and user.get("email"):
        return _start_mfa(user)
    return _finish_login(user.get("name") or email)


@app.route("/mfa", methods=["GET"])
def mfa_verify():
    if not session.get("mfa"):
        return redirect(url_for("login"))
    email = session["mfa"].get("email", "")
    masked = email
    if "@" in email:
        u, d = email.split("@", 1)
        masked = (u[:2] + "•••") + "@" + d
    return render_template("mfa.html", email=masked)


@app.route("/mfa", methods=["POST"])
def mfa_check():
    csrf.protect()
    challenge = session.get("mfa")
    code = request.form.get("code", "")
    ok, reason = auth_mfa.verify(challenge, code)
    if ok:
        name = session.get("mfa_name", "Usuário")
        session.pop("mfa", None)
        session.pop("mfa_name", None)
        return _finish_login(name)
    # incrementa tentativas e persiste
    if challenge:
        challenge["attempts"] = challenge.get("attempts", 0) + 1
        session["mfa"] = challenge
    email = (challenge or {}).get("email", "")
    masked = email
    if "@" in email:
        u, d = email.split("@", 1)
        masked = (u[:2] + "•••") + "@" + d
    return render_template("mfa.html", email=masked, error=reason)


@app.route("/mfa/resend", methods=["POST"])
def mfa_resend():
    csrf.protect()
    challenge = session.get("mfa")
    if not challenge:
        return redirect(url_for("login"))
    email = challenge.get("email")
    new_challenge, code = auth_mfa.make_challenge(email)
    session["mfa"] = new_challenge
    auth_mfa.send_code(email, code)
    return redirect(url_for("mfa_verify"))