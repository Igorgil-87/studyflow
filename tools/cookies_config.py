"""
tools/cookies_config.py — resolve o cookies.txt do yt-dlp em tempo real.

Prioridade:
  1) COOKIES_FILE no .env, se apontar pra um arquivo que existe.
  2) cookies.txt na raiz do projeto — é onde a tela de Configurações
     salva quando o usuário faz upload pela interface.

Importante: isso é avaliado a cada chamada (não uma vez só quando o app
sobe), então um upload novo pela interface passa a valer imediatamente,
sem precisar reiniciar o servidor.
"""

import datetime
import os

DEFAULT_COOKIES_PATH = "cookies.txt"

# Tamanho máximo aceito no upload (cookies.txt de verdade tem poucos KB;
# isso é só uma trava de sanidade contra upload de arquivo errado/gigante).
MAX_COOKIES_FILE_BYTES = 512 * 1024  # 512KB


def get_cookies_file() -> str:
    """Caminho do cookies.txt a usar agora, ou "" se nenhum configurado."""
    env_path = os.getenv("COOKIES_FILE", "").strip()
    if env_path and os.path.exists(env_path):
        return env_path
    if os.path.exists(DEFAULT_COOKIES_PATH):
        return DEFAULT_COOKIES_PATH
    return ""


def cookies_status() -> dict:
    """Pra tela de Configurações mostrar se está configurado e desde quando."""
    path = get_cookies_file()
    if not path:
        return {"configured": False, "updated_em": None}
    mtime = os.path.getmtime(path)
    updated = datetime.datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
    return {"configured": True, "updated_em": updated}


def save_uploaded_cookies(file_bytes: bytes) -> None:
    """Valida e salva o cookies.txt enviado pela tela de Configurações.
    Levanta ValueError com mensagem segura de mostrar ao usuário se algo
    estiver errado."""
    if not file_bytes:
        raise ValueError("Arquivo vazio.")
    if len(file_bytes) > MAX_COOKIES_FILE_BYTES:
        raise ValueError("Arquivo grande demais pra ser um cookies.txt de verdade "
                          f"(máximo {MAX_COOKIES_FILE_BYTES // 1024}KB).")
    try:
        text = file_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise ValueError("Arquivo não parece ser um cookies.txt em texto (formato Netscape).")
    # Verificação leve de formato: cookies.txt Netscape começa com esse
    # cabeçalho, ou tem linhas TAB-separadas com "youtube.com".
    if "# Netscape" not in text and "youtube.com" not in text:
        raise ValueError("Arquivo não parece ser um cookies.txt exportado do YouTube. "
                          "Confirme que exportou com a aba do YouTube aberta.")
    # Em produção COOKIES_FILE pode apontar para um volume compartilhado
    # entre web e worker (ex.: /app/secrets/cookies.txt). Assim, um upload
    # feito pela UI passa a valer também para os workers sem rebuild.
    target = os.getenv("COOKIES_FILE", "").strip() or DEFAULT_COOKIES_PATH
    parent = os.path.dirname(target)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = f"{target}.tmp"
    with open(tmp, "wb") as f:
        f.write(file_bytes)
    os.replace(tmp, target)
