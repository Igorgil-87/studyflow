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

# CSRF só nos formulários HTML reais (login/signup/MFA); rotas de
# API/AJAX ficam de fora, protegidas por login_required + sessão.
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


@app.route("/auth/<provider>")
def oauth_login(provider):
    if provider not in OAUTH_PROVIDERS or oauth is None:
        return render_template(
            "login.html", providers=OAUTH_PROVIDERS,
            error=f"Login com {provider.title()} ainda não configurado. "
                  "Veja OAUTH_LOGIN_SETUP.md."), 200
    client = getattr(oauth, provider)
    redirect_uri = url_for("oauth_callback", provider=provider, _external=True)
    return client.authorize_redirect(redirect_uri)


@app.route("/auth/<provider>/callback")
def oauth_callback(provider):
    if provider not in OAUTH_PROVIDERS or oauth is None:
        return redirect(url_for("login"))
    try:
        client = getattr(oauth, provider)
        token = client.authorize_access_token()
        info = auth_oauth.extract_userinfo(provider, oauth, token)
        if not info.get("provider_id"):
            raise RuntimeError("provedor não retornou identificador")
        user = auth_users.upsert_oauth_user(
            provider, info["provider_id"], info.get("email"), info.get("name"))
        return _finish_login(user.get("name") or user.get("email") or provider)
    except Exception as e:
        print(f"[oauth] callback {provider} falhou: {e}")
        return render_template(
            "login.html", providers=OAUTH_PROVIDERS,
            error=f"Falha no login com {provider.title()}. Tente novamente."), 200


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Páginas dos módulos ──────────────────────────────────────────────────
@app.route("/curso")
@login_required
def curso():
    return render_template("curso.html")


# ══════════ Catálogo de cursos (enterprise) ══════════
@app.route("/catalogo")
@login_required
def catalogo():
    import catalog
    return render_template("catalogo.html", cursos=catalog.all_courses(),
                           categorias=catalog.CATEGORIAS, niveis=catalog.NIVEIS)


@app.route("/api/catalogo")
@login_required
def api_catalogo():
    import catalog
    return jsonify({"cursos": catalog.all_courses()})


# ══════════ Trilhas (funcionalidade real, persistida por usuário) ══════════
@app.route("/trilhas")
@login_required
def trilhas():
    import catalog
    return render_template("trilhas.html", cursos=catalog.all_courses())


# ══════════ Módulo Planejamento (atividades: board + calendário) ══════════
@app.route("/configuracoes")
@login_required
def configuracoes():
    return render_template(
        "configuracoes.html",
        username=session.get("user", ""),
        mfa_enabled=auth_mfa.is_enabled(),
    )


@app.route("/api/configuracoes/senha", methods=["POST"])
@login_required
def configuracoes_trocar_senha():
    body = request.get_json(force=True, silent=True) or {}
    senha_atual = body.get("senha_atual", "")
    senha_nova = body.get("senha_nova", "")
    email = session.get("user", "")
    try:
        auth_users.change_password(email, senha_atual, senha_nova)
        return jsonify({"ok": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/planejamento")
@login_required
def planejamento():
    return render_template("planejamento.html")


@app.route("/automacoes")
@login_required
def automacoes():
    return render_template("automacoes.html")


@app.route("/api/planejamento/atividades", methods=["GET"])
@login_required
def api_planejamento_list():
    from planning import store
    try:
        return jsonify({"atividades": store.list_atividades()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/planejamento/atividades", methods=["POST"])
@login_required
def api_planejamento_create():
    from planning import store
    body = request.get_json(force=True, silent=True) or {}
    try:
        atividade = store.create_atividade(
            body.get("titulo", ""),
            descricao=body.get("descricao", ""),
            status=body.get("status", "ideia"),
            tipo=body.get("tipo", "video"),
            pilar=body.get("pilar", ""),
            data_pub=body.get("data_pub"),
            video_id=body.get("video_id"),
            carrossel_job_id=body.get("carrossel_job_id"),
            modulo=body.get("modulo", "geral"),
            hora_inicio=body.get("hora_inicio"),
            duracao_min=body.get("duracao_min"),
            campos_extra=body.get("campos_extra"),
        )
        return jsonify({"atividade": atividade}), 201
    except store.PlanningError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/planejamento/atividades/<atividade_id>", methods=["PATCH"])
@login_required
def api_planejamento_update(atividade_id):
    from planning import store
    body = request.get_json(force=True, silent=True) or {}
    try:
        atividade = store.update_atividade(atividade_id, **body)
        return jsonify({"atividade": atividade})
    except store.PlanningError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/planejamento/atividades/<atividade_id>", methods=["DELETE"])
@login_required
def api_planejamento_delete(atividade_id):
    from planning import store
    try:
        store.delete_atividade(atividade_id)
        return jsonify({"ok": True})
    except store.PlanningError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _trilhas_user_key():
    return session.get("user", "anon")


@app.route("/api/trilhas", methods=["GET"])
@login_required
def api_trilhas_list():
    from auth.prefs import get_pref
    trilhas = get_pref(_trilhas_user_key(), "trilhas", default=[]) or []
    return jsonify({"trilhas": trilhas})


@app.route("/api/trilhas", methods=["POST"])
@login_required
def api_trilhas_create():
    from auth.prefs import get_pref, set_pref
    import catalog, time
    data = request.get_json(silent=True) or {}
    nome = (data.get("nome") or "").strip()
    curso_ids = data.get("cursos") or []
    if not nome:
        return jsonify({"error": "Dê um nome à trilha."}), 400
    if not curso_ids:
        return jsonify({"error": "Escolha ao menos um curso."}), 400
    # valida ids e calcula carga horária
    validos = [c for c in curso_ids if catalog.by_id(c)]
    horas = sum(catalog.by_id(c)["horas"] for c in validos)
    trilhas = get_pref(_trilhas_user_key(), "trilhas", default=[]) or []
    trilhas.append({
        "id": f"t{int(time.time())}",
        "nome": nome,
        "cursos": validos,
        "horas": horas,
        "criada_em": time.strftime("%Y-%m-%d"),
    })
    set_pref(_trilhas_user_key(), "trilhas", trilhas)
    return jsonify({"ok": True, "trilhas": trilhas})


@app.route("/api/trilhas/<trilha_id>", methods=["DELETE"])
@login_required
def api_trilhas_delete(trilha_id):
    from auth.prefs import get_pref, set_pref
    trilhas = get_pref(_trilhas_user_key(), "trilhas", default=[]) or []
    trilhas = [t for t in trilhas if t.get("id") != trilha_id]
    set_pref(_trilhas_user_key(), "trilhas", trilhas)
    return jsonify({"ok": True, "trilhas": trilhas})


# ══════════ Curso em andamento (último curso gerado) ══════════
@app.route("/api/curso-atual", methods=["GET"])
@login_required
def api_curso_atual():
    from auth.prefs import get_pref
    atual = get_pref(_trilhas_user_key(), "curso_atual", default=None)
    return jsonify({"curso": atual})


@app.route("/api/curso-atual", methods=["POST"])
@login_required
def api_curso_atual_save():
    from auth.prefs import set_pref
    import time
    data = request.get_json(silent=True) or {}
    titulo = (data.get("titulo") or "").strip()
    if not titulo:
        return jsonify({"error": "sem título"}), 400
    curso = {
        "titulo": titulo,
        "subtitulo": (data.get("subtitulo") or "Curso gerado por IA").strip(),
        "progresso": int(data.get("progresso", 0)),
        "aula_atual": (data.get("aula_atual") or "").strip(),
        "atualizado_em": time.strftime("%Y-%m-%d %H:%M"),
    }
    set_pref(_trilhas_user_key(), "curso_atual", curso)
    return jsonify({"ok": True, "curso": curso})


# ══════════ Eventos (listar, criar, excluir — persistido por usuário) ══════════
@app.route("/eventos")
@login_required
def eventos():
    return render_template("eventos.html")


@app.route("/api/eventos", methods=["GET"])
@login_required
def api_eventos_list():
    from auth.prefs import get_pref
    eventos = get_pref(_trilhas_user_key(), "eventos", default=[]) or []
    eventos.sort(key=lambda e: (e.get("data", ""), e.get("hora", "")))
    return jsonify({"eventos": eventos})


@app.route("/api/eventos", methods=["POST"])
@login_required
def api_eventos_create():
    from auth.prefs import get_pref, set_pref
    import time
    data = request.get_json(silent=True) or {}
    titulo = (data.get("titulo") or "").strip()
    dia = (data.get("data") or "").strip()  # YYYY-MM-DD
    if not titulo:
        return jsonify({"error": "Dê um título ao evento."}), 400
    if not dia:
        return jsonify({"error": "Escolha uma data."}), 400
    eventos = get_pref(_trilhas_user_key(), "eventos", default=[]) or []
    eventos.append({
        "id": f"e{int(time.time()*1000)}",
        "titulo": titulo,
        "data": dia,
        "hora": (data.get("hora") or "").strip(),
        "tipo": (data.get("tipo") or "aula").strip(),
        "nota": (data.get("nota") or "").strip(),
    })
    set_pref(_trilhas_user_key(), "eventos", eventos)
    return jsonify({"ok": True, "eventos": eventos})


@app.route("/api/eventos/<evento_id>", methods=["DELETE"])
@login_required
def api_eventos_delete(evento_id):
    from auth.prefs import get_pref, set_pref
    eventos = get_pref(_trilhas_user_key(), "eventos", default=[]) or []
    eventos = [e for e in eventos if e.get("id") != evento_id]
    set_pref(_trilhas_user_key(), "eventos", eventos)
    return jsonify({"ok": True, "eventos": eventos})


# ══════════ Certificados (marcar conclusão + gerar PNG) ══════════
@app.route("/certificados")
@login_required
def certificados():
    return render_template("certificados.html", username=session.get("user", ""))


@app.route("/api/concluidos", methods=["GET"])
@login_required
def api_concluidos_list():
    from auth.prefs import get_pref
    concluidos = get_pref(_trilhas_user_key(), "concluidos", default=[]) or []
    concluidos.sort(key=lambda c: c.get("data", ""), reverse=True)
    return jsonify({"concluidos": concluidos})


@app.route("/api/concluidos", methods=["POST"])
@login_required
def api_concluidos_create():
    from auth.prefs import get_pref, set_pref
    import time
    data = request.get_json(silent=True) or {}
    curso = (data.get("curso") or "").strip()
    if not curso:
        return jsonify({"error": "Informe o curso concluído."}), 400
    concluidos = get_pref(_trilhas_user_key(), "concluidos", default=[]) or []
    # evita duplicar o mesmo curso
    if any(c.get("curso") == curso for c in concluidos):
        return jsonify({"ok": True, "concluidos": concluidos, "dup": True})
    concluidos.append({
        "id": f"c{int(time.time()*1000)}",
        "curso": curso,
        "nota": (data.get("nota") or "").strip(),
        "data": time.strftime("%d/%m/%Y"),
    })
    set_pref(_trilhas_user_key(), "concluidos", concluidos)
    return jsonify({"ok": True, "concluidos": concluidos})


@app.route("/api/concluidos/<cid>", methods=["DELETE"])
@login_required
def api_concluidos_delete(cid):
    from auth.prefs import get_pref, set_pref
    concluidos = get_pref(_trilhas_user_key(), "concluidos", default=[]) or []
    concluidos = [c for c in concluidos if c.get("id") != cid]
    set_pref(_trilhas_user_key(), "concluidos", concluidos)
    return jsonify({"ok": True, "concluidos": concluidos})


@app.route("/certificado/<cid>.png")
@login_required
def certificado_png(cid):
    from auth.prefs import get_pref
    from flask import Response
    try:
        from certificado import gerar_certificado_png
        concluidos = get_pref(_trilhas_user_key(), "concluidos", default=[]) or []
        c = next((x for x in concluidos if x.get("id") == cid), None)
        if not c:
            print(f"[certificado] id não encontrado: {cid} (tem {len(concluidos)} concluídos)")
            return "Certificado não encontrado", 404
        nome = session.get("user", "Aluno(a)")
        if "@" in nome:
            nome = nome.split("@")[0].replace(".", " ").title()
        png = gerar_certificado_png(nome, c.get("curso", ""), c.get("data", ""),
                                    c.get("nota") or None)
        print(f"[certificado] gerado OK para '{c.get('curso')}' ({len(png)} bytes)")
        return Response(png, mimetype="image/png",
                        headers={"Cache-Control": "no-store"})
    except Exception as e:
        import traceback
        print(f"[certificado] ERRO ao gerar: {type(e).__name__}: {e}")
        traceback.print_exc()
        return f"Erro ao gerar certificado: {e}", 500


@app.route("/youtuber")
@login_required
def youtuber():
    return render_template("youtuber.html")


@app.route("/trends")
@login_required
def trends():
    return render_template("trends.html")


# ══════════ Módulo Estúdio / Criador (MoneyPrinterTurbo) ══════════
@app.route("/estudio")
@login_required
def estudio():
    return render_template("estudio.html")


@app.route("/api/estudio", methods=["POST"])
@login_required
def api_estudio():
    body = request.get_json(force=True, silent=True) or {}
    subject = (body.get("subject") or "").strip()
    if not subject:
        return jsonify({"error": "Tema obrigatório"}), 400

    job_id = uuid.uuid4().hex
    jobs.create(job_id, kind="estudio")
    dispatch("pipelines.run_estudio_pipeline", job_id, subject, {
        "script":   (body.get("script") or "").strip(),
        "aspect":   body.get("aspect", "9:16"),
        "voice":    body.get("voice", "pt-BR-AntonioNeural-Male"),
        "count":    int(body.get("count", 1)),
        "language": body.get("language", "pt-BR"),
    })
    return jsonify({"job_id": job_id})


# ══════════ Módulo Criador · Imagens (Fooocus-API) ══════════
@app.route("/api/imagem", methods=["POST"])
@login_required
def api_imagem():
    body = request.get_json(force=True, silent=True) or {}
    prompt = (body.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "Descreva a imagem que você quer gerar"}), 400

    preset = body.get("preset", "thumbnail")
    if preset not in ("thumbnail", "carrossel", "capa"):
        return jsonify({"error": "Preset inválido"}), 400

    engine = body.get("engine", "fooocus")
    if engine not in ("fooocus", "openai"):
        return jsonify({"error": "Motor inválido"}), 400

    ai_copy = bool(body.get("ai_copy"))
    if ai_copy and preset != "carrossel":
        return jsonify({"error": "Texto de impacto automático só funciona no preset Carrossel"}), 400

    ref_images = body.get("reference_images_b64") or []
    if not isinstance(ref_images, list):
        return jsonify({"error": "reference_images_b64 precisa ser uma lista"}), 400
    if len(ref_images) > 16:
        return jsonify({"error": "Máximo de 16 imagens de referência"}), 400

    job_id = uuid.uuid4().hex
    jobs.create(job_id, kind="imagem")
    dispatch("pipelines.run_imagem_pipeline", job_id, prompt, {
        "preset": preset,
        "engine": engine,
        "negative_prompt": (body.get("negative_prompt") or "").strip(),
        # imagens de referência (base64, sem o prefixo "data:image/...;base64,"
        # — o front remove isso antes de mandar) — só motor openai
        "reference_images_b64": [r.strip() for r in ref_images if r.strip()] or None,
        # texto de impacto automático (Claude) aplicado por cima do fundo
        "ai_copy": ai_copy,
        "pilar": (body.get("pilar") or "").strip(),
        "topic": (body.get("topic") or "").strip() or prompt,
    })
    return jsonify({"job_id": job_id})


@app.route("/api/instagram/publicar", methods=["POST"])
@login_required
def api_instagram_publicar():
    body = request.get_json(force=True, silent=True) or {}
    image_paths = body.get("images") or []
    if not image_paths:
        return jsonify({"error": "Nenhuma imagem para publicar"}), 400
    if len(image_paths) > 10:
        return jsonify({"error": "Carrossel aceita no máximo 10 imagens"}), 400

    job_id = uuid.uuid4().hex
    jobs.create(job_id, kind="instagram_publish")
    dispatch("pipelines.run_instagram_publish_pipeline", job_id, image_paths,
             (body.get("caption") or "").strip())
    return jsonify({"job_id": job_id})


# ── API: Curso ───────────────────────────────────────────────────────────
@app.route("/api/generate", methods=["POST"])
@login_required
def generate():
    body = request.get_json(force=True)
    topic = (body.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "Tema obrigatório"}), 400

    num_flashcards = int(body.get("flashcards", 5))
    num_questions = int(body.get("questions", 5))

    job_id = uuid.uuid4().hex
    jobs.create(job_id, kind="curso")
    dispatch("pipelines.run_curso_pipeline",
             job_id, topic, num_flashcards, num_questions)
    return jsonify({"job_id": job_id})


# ── API: Youtuber ────────────────────────────────────────────────────────
@app.route("/api/youtuber/trends", methods=["POST"])
@login_required
def youtuber_trends():
    body = request.get_json(force=True)
    niche = (body.get("niche") or "").strip()
    if not niche:
        return jsonify({"error": "Nicho obrigatório"}), 400

    fetcher = TrendFetcherTool(cookies_browser=COOKIES_BROWSER)
    result = fetcher._run(niche=niche)
    if result.startswith("ERRO"):
        return jsonify({"error": result}), 500
    return jsonify(json.loads(result))


@app.route("/api/youtuber/topic-videos", methods=["POST"])
@login_required
def youtuber_topic_videos():
    body = request.get_json(force=True)
    topic = (body.get("topic") or "").strip()
    niche = (body.get("niche") or "").strip()
    if not topic:
        return jsonify({"error": "assunto (topic) é obrigatório"}), 400

    from tools import YouTubeSearchTool
    from tools.topic_video_finder import find_relevant_videos
    from obs.tracing import traced_llm

    search = YouTubeSearchTool()

    def search_fn(q, n):
        # suffix="" → busca crua do assunto (sem forçar "tutorial")
        return search._run(query=q, max_results=n, suffix="")

    def _call_llm(prompt):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=LLM_MODEL, temperature=0).invoke(prompt).content

    def llm_fn(prompt):
        # relevância passa pelo tracing → custo/latência aparecem no /obs.
        # fail-open: se o LLM falhar, retorna "" e o finder entrega os crus.
        return traced_llm(
            "openai", "topic_relevance", LLM_MODEL, _call_llm, prompt,
            trace_id="topic-search", input_text=prompt, timeout=60, fallback="",
        )

    try:
        result = find_relevant_videos(topic, niche, search_fn, llm_fn)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/youtuber/vertical", methods=["POST"])
@login_required
def youtuber_vertical():
    import os
    from tools.vertical_export import export_vertical, check_ffmpeg
    if not check_ffmpeg():
        return jsonify({"ok": False, "erro": "ffmpeg não encontrado. Instale com "
                        "'brew install ffmpeg' (macOS) e reinicie o app."}), 400
    body = request.get_json(force=True)
    arquivo = (body.get("arquivo") or "").strip()
    mode = body.get("mode", "blur")
    if not arquivo:
        return jsonify({"ok": False, "erro": "arquivo não informado"}), 400

    # Valida o caminho de entrada: precisa ficar dentro de static/
    # (evita path traversal via "../../..." no campo arquivo).
    static_base = os.path.normpath("static")
    src = os.path.normpath(os.path.join(static_base, arquivo))
    if not src.startswith(static_base + os.sep) or not os.path.isfile(src):
        return jsonify({"ok": False, "erro": "clip inválido ou não encontrado"}), 400

    nome_base, _ = os.path.splitext(arquivo)
    out_rel = f"{nome_base}_9x16.mp4"
    out_abs = os.path.normpath(os.path.join(static_base, out_rel))
    if not out_abs.startswith(static_base + os.sep):
        return jsonify({"ok": False, "erro": "caminho de saída inválido"}), 400
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)

    result = export_vertical(src, out_abs, mode=mode)
    if result.get("ok"):
        return jsonify({"ok": True, "arquivo": out_rel})
    return jsonify(result), 500


@app.route("/api/trends/layout", methods=["GET"])
@login_required
def trends_layout_get():
    from auth import prefs
    user_key = session.get("user", "anon")
    layout = prefs.get_pref(user_key, "mc_layout", default=None)
    return jsonify({"layout": layout})


@app.route("/api/trends/layout", methods=["POST"])
@login_required
def trends_layout_save():
    from auth import prefs
    user_key = session.get("user", "anon")
    data = request.get_json(silent=True) or {}
    layout = data.get("layout")
    # validação leve: precisa ser uma lista de strings (ids dos widgets)
    if not isinstance(layout, list) or not all(isinstance(x, str) for x in layout):
        return jsonify({"ok": False, "erro": "layout inválido"}), 400
    ok = prefs.set_pref(user_key, "mc_layout", layout[:30])
    return jsonify({"ok": ok})


@app.route("/api/trends/nasa", methods=["GET"])
@login_required
def trends_nasa():
    from tools.nasa_source import fetch_apod
    try:
        apod = fetch_apod()
        return jsonify({"apod": apod})
    except Exception as e:
        return jsonify({"apod": None, "error": str(e)})


@app.route("/api/trends/hackernews", methods=["GET"])
@login_required
def trends_hackernews():
    from tools.hackernews_source import fetch_top
    try:
        stories = fetch_top(limit=6)
        return jsonify({"stories": stories})
    except Exception as e:
        return jsonify({"stories": [], "error": str(e)})


@app.route("/api/trends/github", methods=["GET"])
@login_required
def trends_github():
    from tools.github_source import fetch_trending
    try:
        repos = fetch_trending(days=7, limit=6)
        return jsonify({"repos": repos})
    except Exception as e:
        return jsonify({"repos": [], "error": str(e)})


@app.route("/api/trends/weather", methods=["GET"])
@login_required
def trends_weather():
    from tools.weather_source import fetch_weather
    city = request.args.get("city")
    data = fetch_weather(city=city)
    return jsonify({"weather": data})


@app.route("/api/trends/economy", methods=["GET"])
@login_required
def trends_economy():
    from tools.economy_source import fetch_quotes, fetch_stocks, format_quote
    quotes = []
    err = []
    # câmbio (AwesomeAPI, sem token) e ações (brapi, pode pedir token) — independentes
    try:
        for q in fetch_quotes():
            q["display"] = format_quote(q)
            quotes.append(q)
    except Exception as e:
        err.append(f"cambio: {e}")
    try:
        for q in fetch_stocks():
            q["display"] = format_quote(q)
            quotes.append(q)
    except Exception as e:
        err.append(f"acoes: {e}")
    return jsonify({"quotes": quotes, "error": "; ".join(err)})


@app.route("/api/youtuber/people-search", methods=["POST"])
@login_required
def youtuber_people_search():
    body = request.get_json(force=True)
    person = (body.get("person") or "").strip()
    topic = (body.get("topic") or "").strip()
    prefer_podcast = body.get("prefer_podcast", True)
    if not person and not topic:
        return jsonify({"error": "Informe uma pessoa ou um assunto"}), 400

    from tools import YouTubeSearchTool
    from tools.people_podcast_finder import find_people_videos

    search = YouTubeSearchTool()

    def search_fn(q, n):
        return search._run(query=q, max_results=n, suffix="")

    try:
        result = find_people_videos(person, topic, search_fn,
                                    prefer_podcast=bool(prefer_podcast))
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/youtuber/generate", methods=["POST"])
@login_required
def youtuber_generate():
    body = request.get_json(force=True)
    niche = (body.get("niche") or "").strip()
    video_url = (body.get("video_url") or "").strip()
    content_type = (body.get("content_type") or "shorts").strip()
    if not niche or not video_url:
        return jsonify({"error": "Nicho e URL do vídeo são obrigatórios"}), 400

    # Quantidade de cortes (opcional): 1 a 10. Vazio = a IA decide pela faixa.
    num_clips = body.get("num_clips")
    try:
        num_clips = max(1, min(15, int(num_clips))) if num_clips else None
    except (TypeError, ValueError):
        num_clips = None

    # Legenda: liga/desliga + tradução opcional (ex: vídeo em inglês,
    # legenda queimada em português). idioma_legenda=None significa "sem
    # tradução" (legenda no idioma que o Whisper transcreveu, original).
    gerar_legenda = bool(body.get("gerar_legenda", True))
    idioma_legenda = (body.get("idioma_legenda") or "").strip() or None
    if idioma_legenda not in (None, "pt", "en", "es"):
        idioma_legenda = None

    # Fechamento/identidade — cola static/video/fechamento.mp4 no final
    # de todo clip (Short ou Corte). Ligado por padrão.
    adicionar_fechamento = bool(body.get("adicionar_fechamento", True))

    job_id = uuid.uuid4().hex
    jobs.create(job_id, kind="youtuber")
    dispatch("pipelines.run_youtuber_pipeline",
             job_id, niche, video_url, content_type, num_clips,
             gerar_legenda, idioma_legenda, adicionar_fechamento)
    return jsonify({"job_id": job_id})


@app.route("/api/youtuber/publish", methods=["POST"])
@login_required
def youtuber_publish():
    body = request.get_json(force=True)
    arquivo = (body.get("arquivo") or "").strip()
    if not arquivo:
        return jsonify({"error": "arquivo do clip é obrigatório"}), 400

    # Resolve e valida o caminho: deve estar dentro de static/videos.
    safe = os.path.normpath(os.path.join("static", arquivo))
    base = os.path.normpath("static/videos")
    if not safe.startswith(base + os.sep) or not os.path.isfile(safe):
        return jsonify({"error": "clip inválido ou não encontrado"}), 400

    try:
        from publish import youtube_uploader as up
        from publish.auth import NotAuthenticatedError
    except ImportError:
        return jsonify({"error": "Dependências do YouTube ausentes. "
                                 "Rode: pip install -r requirements.txt"}), 500

    try:
        result = up.upload_video(
            video_path=safe,
            title=body.get("titulo") or "Corte",
            hook=body.get("hook") or "",
            hashtags=body.get("hashtags") or [],
            privacy=body.get("privacy"),
        )
        # Registra a previsão da IA (viral_score, hook, thumbnail) junto
        # com o video_id real — fecha o loop pra comparar com o resultado
        # de verdade depois (Sprint 2: YouTube Analytics). Fail-open: se
        # isso falhar, a publicação JÁ ACONTECEU, não faz sentido dar erro
        # pro usuário por causa só do registro de telemetria.
        try:
            from analytics.store import registrar_publicacao
            registrar_publicacao(
                "youtube", result["video_id"], url=result.get("url", ""),
                modulo="youtuber", titulo=body.get("titulo") or "",
                hook=body.get("hook") or "", viral_score=body.get("viral_score"),
                tier=body.get("tier"), thumb_texto=body.get("thumb_texto") or "",
                thumb_emocao=body.get("thumb_emocao") or "",
            )
        except Exception as e:
            print(f"[analytics] Falha ao registrar previsão (publicação seguiu normal): {e}")
        return jsonify(result)
    except NotAuthenticatedError as e:
        return jsonify({"error": str(e), "need_auth": True}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/youtuber/publish_instagram", methods=["POST"])
@login_required
def youtuber_publish_instagram():
    body = request.get_json(force=True)
    arquivo = (body.get("arquivo") or "").strip()
    if not arquivo:
        return jsonify({"error": "arquivo do clip é obrigatório"}), 400

    # Mesma validação de caminho seguro da rota do YouTube.
    safe = os.path.normpath(os.path.join("static", arquivo))
    base = os.path.normpath("static/videos")
    if not safe.startswith(base + os.sep) or not os.path.isfile(safe):
        return jsonify({"error": "clip inválido ou não encontrado"}), 400

    from tools import cloudinary_client, instagram_client

    if not cloudinary_client.is_alive():
        return jsonify({
            "error": "Cloudinary não configurado — defina CLOUDINARY_CLOUD_NAME, "
                     "CLOUDINARY_API_KEY e CLOUDINARY_API_SECRET no .env."
        }), 400
    if not instagram_client.is_alive():
        return jsonify({
            "error": "Instagram não configurado — defina IG_BUSINESS_ACCOUNT_ID "
                     "e IG_ACCESS_TOKEN no .env."
        }), 400

    titulo = (body.get("titulo") or "").strip()
    hook = (body.get("hook") or "").strip()
    hashtags = body.get("hashtags") or []
    tag_line = " ".join(f"#{h.lstrip('#')}" for h in hashtags if h)
    caption = "\n\n".join(p for p in [titulo, hook, tag_line] if p)[:2200]  # limite de caption do IG

    try:
        video_url = cloudinary_client.upload_video(safe)
        media_id = instagram_client.publish_reel(video_url, caption)
        try:
            from analytics.store import registrar_publicacao
            registrar_publicacao(
                "instagram", media_id, modulo="youtuber",
                titulo=titulo, hook=hook, viral_score=body.get("viral_score"),
                tier=body.get("tier"), thumb_texto=body.get("thumb_texto") or "",
                thumb_emocao=body.get("thumb_emocao") or "",
            )
        except Exception as e:
            print(f"[analytics] Falha ao registrar previsão (publicação seguiu normal): {e}")
        return jsonify({"ok": True, "media_id": media_id})
    except (cloudinary_client.CloudinaryUploadError, instagram_client.InstagramPublishError) as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: Tendências ──────────────────────────────────────────────────────
@app.route("/api/trends/analyze", methods=["POST"])
@login_required
def analyze_trends():
    body = request.get_json(force=True)
    cats = body.get("categories") or list(TREND_CATEGORIES.keys())
    urls = [u.strip() for u in (body.get("urls") or []) if u.strip()][:5]  # máx 5 por vez

    job_id = uuid.uuid4().hex
    jobs.create(job_id, kind="trends")
    dispatch("pipelines.run_global_trends_pipeline", job_id, cats, urls)
    return jsonify({"job_id": job_id})


# ── SSE compartilhado ────────────────────────────────────────────────────
@app.route("/api/stream/<job_id>")
@login_required
def stream(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        return jsonify({"error": "Job não encontrado"}), 404

    def event_stream():
        # Se o job JÁ tinha terminado antes dessa conexão SSE existir
        # (reload de página, aba fechada e reaberta, conexão caiu e o
        # navegador reconectou sozinho, etc.) — o bus é pub/sub PURO, sem
        # histórico, então o evento "complete"/"error" original já foi
        # publicado e perdido pra sempre. Sem isso aqui, a tela fica
        # "Processando..." pra sempre mesmo com o resultado pronto no
        # backend (foi exatamente isso que aconteceu no módulo Youtuber
        # em 30/07/2026 — o log confirmava "Job OK", mas a tela nunca
        # soube). Reconstrói o evento final a partir do que já está
        # persistido — os pipelines guardam (via jobs.set) exatamente os
        # mesmos campos que publicam no "complete" ao vivo.
        if job.get("done"):
            if job.get("error"):
                yield sse("pipeline_error", {"message": job["error"]})
            else:
                payload = {k: v for k, v in job.items() if k not in ("kind", "done", "error")}
                yield sse("complete", payload)
            yield sse("end", {})
            return

        for event, data in bus.subscribe(job_id):
            if event == "__end__":
                yield sse("end", {})
                break
            yield sse(event, data)

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.route("/api/quiz/<job_id>")
@login_required
def get_quiz(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job não encontrado"}), 404
    if job.get("error"):
        return jsonify({"error": job["error"]}), 500
    if not job.get("quiz"):
        return jsonify({"error": "Quiz ainda não pronto"}), 202
    return jsonify(job["quiz"])


# ── Observabilidade + Evals + Feedback ───────────────────────────────────
@app.route("/obs")
@login_required
def obs_dashboard():
    return render_template("obs.html")


@app.route("/api/observability/summary")
@login_required
def observability_summary():
    data = obs_report.summary()
    # Enriquece o RAG com a contagem de chunks na base vetorial (best-effort).
    try:
        from rag.store import get_store
        st = get_store()
        data["rag"]["indexed_chunks"] = st.count() if st else None
    except Exception:
        data["rag"]["indexed_chunks"] = None
    return jsonify(data)


@app.route("/api/observability/logs")
@login_required
def observability_logs():
    try:
        limit = max(1, min(500, int(request.args.get("limit", 100))))
    except (TypeError, ValueError):
        limit = 100
    return jsonify({"logs": obs_report.recent_logs(limit)})


@app.route("/api/observability/evals")
@login_required
def observability_evals():
    return jsonify({"evals": obs_report.recent_evals(20)})


@app.route("/api/observability/errors")
@login_required
def observability_errors():
    return jsonify({"errors": obs_report.errors_recent(50)})


@app.route("/rag")
@login_required
def rag_page():
    return render_template("rag.html")


@app.route("/api/rag/query", methods=["POST"])
@login_required
def rag_query():
    body = request.get_json(force=True)
    pergunta = (body.get("pergunta") or "").strip()
    video_id = (body.get("video_id") or "").strip() or None
    if not pergunta:
        return jsonify({"error": "pergunta é obrigatória"}), 400

    try:
        from rag.store import get_store
        from rag.query import answer
        from cache.embeddings import embed
        from obs.tracing import traced_llm
    except ImportError as e:
        return jsonify({"error": f"Dependências do RAG ausentes: {e}"}), 500

    store = get_store()
    if store is None:
        return jsonify({
            "answer": None,
            "error": "RAG desligado ou Postgres/pgvector indisponível. "
                     "Veja RAG_PGVECTOR.md.",
            "sources": [],
        }), 200

    def _call_llm_openai(prompt):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=LLM_MODEL, temperature=0).invoke(prompt).content

    def _call_llm_anthropic(prompt):
        from langchain_anthropic import ChatAnthropic
        model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
        return ChatAnthropic(model=model, temperature=0).invoke(prompt).content

    # RAG_LLM_PROVIDER: "anthropic" (padrão, usa seu ANTHROPIC_API_KEY) ou
    # "openai" — os embeddings continuam via OpenAI de qualquer forma (a
    # Anthropic não tem API própria de embeddings), só a RESPOSTA final
    # muda de modelo.
    _provider = os.getenv("RAG_LLM_PROVIDER", "anthropic").strip().lower()
    _call_llm = _call_llm_openai if _provider == "openai" else _call_llm_anthropic
    _model_label = LLM_MODEL if _provider == "openai" else os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

    def llm_fn(prompt):
        return traced_llm(
            _provider, "rag_answer", _model_label, _call_llm, prompt,
            trace_id="rag", input_text=prompt, timeout=60,
            fallback="(não foi possível gerar a resposta)",
        )

    try:
        result = answer(pergunta, embed, store, llm_fn, video_id=video_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════ Módulo Curso · Material de apoio (PDF/PPTX/DOCX → RAG) ══════════
# Só o Curso tem isso — os outros módulos não precisam de upload de documento.
MATERIAL_MAX_BYTES = 20 * 1024 * 1024  # 20MB


@app.route("/api/curso/material", methods=["POST"])
@login_required
def curso_upload_material():
    from rag.document_extractor import extract_text, DocumentExtractionError, SUPPORTED_EXTENSIONS
    from rag.store import get_store
    from rag.index import index_document

    file = request.files.get("arquivo")
    if not file or not file.filename:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        formatos = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        return jsonify({"error": f"Formato '{ext}' não suportado. Formatos aceitos: {formatos}"}), 400

    content = file.read()
    if len(content) > MATERIAL_MAX_BYTES:
        return jsonify({"error": "Arquivo maior que 20MB — reduz o tamanho e tenta de novo."}), 400

    store = get_store()
    if store is None:
        return jsonify({
            "error": "RAG desligado ou Postgres/pgvector indisponível "
                     "(RAG_ENABLED=1 no .env e Postgres precisam estar de pé)."
        }), 200

    try:
        text = extract_text(file.filename, content)
    except DocumentExtractionError as e:
        return jsonify({"error": str(e)}), 400

    try:
        from cache.embeddings import embed
        doc_id = f"material:{uuid.uuid4().hex[:10]}_{file.filename}"
        n_chunks = index_document(doc_id, text, embed, store)
    except Exception as e:
        return jsonify({"error": f"Falha ao indexar: {e}"}), 500

    return jsonify({
        "ok": True,
        "arquivo": file.filename,
        "doc_id": doc_id,
        "chunks_indexados": n_chunks,
        "caracteres_extraidos": len(text),
    })


@app.route("/api/curso/material_url", methods=["POST"])
@login_required
def curso_index_url():
    from tools.crawler_client import crawl_url, CrawlerError, is_alive as crawler_alive
    from rag.store import get_store
    from rag.index import index_document

    body = request.get_json(force=True, silent=True) or {}
    url = (body.get("url") or "").strip()
    if not url:
        return jsonify({"error": "URL é obrigatória"}), 400
    if not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"error": "URL precisa começar com http:// ou https://"}), 400

    if not crawler_alive():
        return jsonify({
            "error": "crawl4ai não instalado. pip install crawl4ai && crawl4ai-setup"
        }), 200

    store = get_store()
    if store is None:
        return jsonify({
            "error": "RAG desligado ou Postgres/pgvector indisponível "
                     "(RAG_ENABLED=1 no .env e Postgres precisam estar de pé)."
        }), 200

    try:
        text = crawl_url(url)
    except CrawlerError as e:
        return jsonify({"error": str(e)}), 500

    if not text:
        return jsonify({"error": "Não consegui extrair conteúdo dessa URL (página vazia, bloqueada ou erro de carregamento)."}), 400

    try:
        from cache.embeddings import embed
        doc_id = f"material:url_{uuid.uuid4().hex[:10]}"
        n_chunks = index_document(doc_id, text, embed, store)
    except Exception as e:
        return jsonify({"error": f"Falha ao indexar: {e}"}), 500

    return jsonify({
        "ok": True,
        "url": url,
        "doc_id": doc_id,
        "chunks_indexados": n_chunks,
        "caracteres_extraidos": len(text),
    })


@app.route("/api/observability/drift")
@login_required
def observability_drift():
    return jsonify(obs_drift.compute())


@app.route("/api/observability/drift/check", methods=["POST"])
@login_required
def observability_drift_check():
    return jsonify(obs_drift.run_check())


@app.route("/api/observability/drift/history")
@login_required
def observability_drift_history():
    return jsonify({"runs": obs_drift.history(limit=20)})


@app.route("/api/analytics/publicacoes")
@login_required
def analytics_publicacoes():
    from analytics.store import list_publicacoes
    modulo = request.args.get("modulo")
    plataforma = request.args.get("plataforma")
    try:
        return jsonify({"publicacoes": list_publicacoes(modulo=modulo, plataforma=plataforma)})
    except Exception as e:
        return jsonify({"error": str(e), "publicacoes": []}), 200


@app.route("/api/analytics/resumo")
@login_required
def analytics_resumo():
    from analytics.store import resumo_por_tier, top_publicacoes_reais
    plataforma = request.args.get("plataforma")
    try:
        return jsonify({
            "por_tier": resumo_por_tier(plataforma=plataforma),
            "top": top_publicacoes_reais(plataforma=plataforma, limit=5),
        })
    except Exception as e:
        return jsonify({"error": str(e), "por_tier": [], "top": []}), 200


@app.route("/api/analytics/atualizar_youtube", methods=["POST"])
@login_required
def analytics_atualizar_youtube():
    try:
        from analytics.youtube_fetcher import atualizar_metricas_pendentes
        resultado = atualizar_metricas_pendentes()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analytics/atualizar_instagram", methods=["POST"])
@login_required
def analytics_atualizar_instagram():
    try:
        from analytics.instagram_fetcher import atualizar_metricas_pendentes
        resultado = atualizar_metricas_pendentes()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/growth/sincronizar_perfil", methods=["POST"])
@login_required
def growth_sincronizar_perfil():
    try:
        from analytics.instagram_profile import sincronizar_perfil_completo
        resultado = sincronizar_perfil_completo()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/growth/analisar_padroes", methods=["POST"])
@login_required
def growth_analisar_padroes():
    try:
        from analytics.growth_analyzer import analisar_pendentes
        resultado = analisar_pendentes(plataforma="instagram")
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/growth/resumo")
@login_required
def growth_resumo():
    from analytics.store import resumo_por_gancho
    try:
        return jsonify({"por_gancho": resumo_por_gancho(plataforma="instagram")})
    except Exception as e:
        return jsonify({"error": str(e), "por_gancho": []}), 200


@app.route("/api/growth/recomendacoes", methods=["POST"])
@login_required
def growth_recomendacoes():
    from analytics.store import resumo_por_gancho, top_publicacoes_reais
    from analytics.growth_analyzer import gerar_recomendacoes
    try:
        por_gancho = resumo_por_gancho(plataforma="instagram")
        top = top_publicacoes_reais(plataforma="instagram", limit=5)
        return jsonify(gerar_recomendacoes(por_gancho, top))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/crescimento")
@login_required
def crescimento():
    return render_template("crescimento.html")


@app.route("/api/feedback", methods=["POST"])
@login_required
def feedback():
    body = request.get_json(force=True)
    trace_id = (body.get("trace_id") or body.get("job_id") or "").strip()
    if not trace_id:
        return jsonify({"error": "trace_id (job_id) obrigatório"}), 400

    raw_vote = body.get("vote")
    vote = 1 if raw_vote in (1, "1", "up", True) else \
        -1 if raw_vote in (-1, "-1", "down", False) else 0
    if vote == 0:
        return jsonify({"error": "vote deve ser 1/up ou -1/down"}), 400

    target = (body.get("target") or "output").strip()
    comment = (body.get("comment") or "").strip()[:1000]
    obs_db.insert_feedback(trace_id, target, vote, comment)
    return jsonify({"ok": True})


# ── Health check (para load balancer / K8s) ──────────────────────────────
@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "mode": config.RUN_MODE})


if __name__ == "__main__":
    Path("output/quizzes").mkdir(parents=True, exist_ok=True)
    Path("output/roadmaps").mkdir(parents=True, exist_ok=True)
    Path("static/videos/highlights").mkdir(parents=True, exist_ok=True)
    Path("static/videos/clips").mkdir(parents=True, exist_ok=True)
    # porta configurável via APP_PORT (default 5001; evita o AirPlay do macOS na 5000)
    _port = int(os.getenv("APP_PORT", "5001"))
    # debug SÓ liga com FLASK_DEBUG=1 explícito — nunca True por padrão
    # (mesmo sendo local-only via __main__, o CodeQL não sabe disso
    # estaticamente, e um literal debug=True é sempre um alerta válido).
    _debug = os.getenv("FLASK_DEBUG", "0") == "1"
    print(f"\nStudyFlow rodando em http://localhost:{_port}  [{config.summary()}]")
    print(f"   LLM: {LLM_MODEL} | Whisper: {WHISPER_MODEL}\n")
    app.run(debug=_debug, threaded=True, port=_port)
