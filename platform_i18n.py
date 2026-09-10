"""Minimal UI internationalization core for StudyFlow pre-auth surfaces.

Language preference precedence:
  explicit ?lang/form lang -> session -> cookie -> Accept-Language -> pt

The preference affects interface copy only; it does not change authentication,
model/provider behavior, or user content.
"""
from __future__ import annotations

SUPPORTED = ("pt", "en", "es")
DEFAULT = "pt"
COOKIE = "studyflow_lang"
HTML_LANG = {"pt": "pt-BR", "en": "en", "es": "es"}

CATALOG = {
    "pt": {
        "language.label": "Idioma",
        "login.title": "StudyFlow · Entrar",
        "login.subtitle": "Seu workspace para aprender, criar e operar com inteligência.",
        "login.google": "Continuar com Google",
        "login.linkedin": "Continuar com LinkedIn",
        "login.instagram": "Continuar com Instagram",
        "login.email_divider": "ou com e-mail",
        "login.email": "E-mail",
        "login.email_placeholder": "voce@email.com",
        "login.password": "Senha",
        "login.password_placeholder": "Sua senha",
        "login.submit": "Entrar",
        "login.name": "Nome",
        "login.name_placeholder": "Como devemos te chamar",
        "login.password_new": "Mínimo 6 caracteres",
        "login.signup": "Criar conta",
        "login.no_account": "Não tem conta?",
        "login.create_now": "Criar agora",
        "login.have_account": "Já tem conta?",
        "login.signup_subtitle": "Crie sua conta em segundos.",
        "auth.invalid": "Usuário ou senha incorretos.",
        "auth.invalid_email": "E-mail inválido.",
        "auth.weak_password": "A senha precisa ter ao menos 6 caracteres.",
        "auth.email_exists": "Este e-mail já está cadastrado.",
    },
    "en": {
        "language.label": "Language",
        "login.title": "StudyFlow · Sign in",
        "login.subtitle": "Your workspace to learn, create, and operate intelligently.",
        "login.google": "Continue with Google",
        "login.linkedin": "Continue with LinkedIn",
        "login.instagram": "Continue with Instagram",
        "login.email_divider": "or use e-mail",
        "login.email": "E-mail",
        "login.email_placeholder": "you@example.com",
        "login.password": "Password",
        "login.password_placeholder": "Your password",
        "login.submit": "Sign in",
        "login.name": "Name",
        "login.name_placeholder": "What should we call you?",
        "login.password_new": "Minimum 6 characters",
        "login.signup": "Create account",
        "login.no_account": "Don't have an account?",
        "login.create_now": "Create one",
        "login.have_account": "Already have an account?",
        "login.signup_subtitle": "Create your account in seconds.",
        "auth.invalid": "Incorrect username or password.",
        "auth.invalid_email": "Invalid e-mail address.",
        "auth.weak_password": "Password must be at least 6 characters.",
        "auth.email_exists": "This e-mail is already registered.",
    },
    "es": {
        "language.label": "Idioma",
        "login.title": "StudyFlow · Iniciar sesión",
        "login.subtitle": "Tu espacio para aprender, crear y operar con inteligencia.",
        "login.google": "Continuar con Google",
        "login.linkedin": "Continuar con LinkedIn",
        "login.instagram": "Continuar con Instagram",
        "login.email_divider": "o con e-mail",
        "login.email": "E-mail",
        "login.email_placeholder": "tu@email.com",
        "login.password": "Contraseña",
        "login.password_placeholder": "Tu contraseña",
        "login.submit": "Iniciar sesión",
        "login.name": "Nombre",
        "login.name_placeholder": "¿Cómo debemos llamarte?",
        "login.password_new": "Mínimo 6 caracteres",
        "login.signup": "Crear cuenta",
        "login.no_account": "¿No tienes una cuenta?",
        "login.create_now": "Crear ahora",
        "login.have_account": "¿Ya tienes una cuenta?",
        "login.signup_subtitle": "Crea tu cuenta en segundos.",
        "auth.invalid": "Usuario o contraseña incorrectos.",
        "auth.invalid_email": "E-mail inválido.",
        "auth.weak_password": "La contraseña debe tener al menos 6 caracteres.",
        "auth.email_exists": "Este e-mail ya está registrado.",
    },
}


def normalize_locale(value: str | None) -> str | None:
    if not value:
        return None
    code = value.strip().lower().replace("_", "-").split("-", 1)[0]
    return code if code in SUPPORTED else None


def tr(locale: str, key: str, **values) -> str:
    loc = normalize_locale(locale) or DEFAULT
    text = CATALOG.get(loc, {}).get(key) or CATALOG[DEFAULT].get(key) or key
    if values:
        try:
            return text.format(**values)
        except (KeyError, ValueError):
            return text
    return text


_LEGACY_AUTH_ERRORS = {
    "E-mail inválido.": "auth.invalid_email",
    "A senha precisa ter ao menos 6 caracteres.": "auth.weak_password",
    "Este e-mail já está cadastrado.": "auth.email_exists",
}


def translate_auth_error(locale: str, message: str) -> str:
    key = _LEGACY_AUTH_ERRORS.get(message)
    return tr(locale, key) if key else message
