"""Classifica erros do yt-dlp e devolve orientação operacional útil."""
from __future__ import annotations


def _runtime_diag() -> str:
    try:
        from tools.youtube_runtime import runtime_status

        st = runtime_status()
        pot = (
            "ok"
            if st.get("pot_provider_plugin")
            and st.get("pot_provider_configured")
            and st.get("pot_provider_reachable") is not False
            else "off/falha"
        )
        return (
            f"yt-dlp={st['yt_dlp']}; "
            f"js_runtime={'ok' if st['js_runtime_ok'] else 'ausente'}; "
            f"cookies_file={'ok' if st['cookies_file_exists'] else 'ausente'}; "
            f"proxy={'on' if st['proxy_configured'] else 'off'}; "
            f"pot_provider={pot}"
        )
    except Exception:
        return "diagnóstico local indisponível"


def classify_download_error(raw_error: str) -> str:
    """Traduz o erro cru sem esconder o detalhe original."""
    erro_lower = (raw_error or "").lower()

    if "private video" in erro_lower:
        return (
            "ERRO: esse vídeo está PRIVADO no YouTube — só quem tem acesso "
            "concedido à conta consegue baixar. Atualizar o yt-dlp não "
            "resolve isso. Se você TEM acesso, configure COOKIES_FILE no "
            ".env com um cookies.txt válido da conta autorizada. "
            f"Detalhe: {raw_error}"
        )

    if "sign in to confirm your age" in erro_lower or (
        "age" in erro_lower and "restrict" in erro_lower
    ):
        return (
            "ERRO: esse vídeo tem restrição de idade no YouTube. Configure "
            "COOKIES_FILE no .env com cookies.txt de uma conta logada e "
            "maior de idade. "
            f"Detalhe: {raw_error}"
        )

    if "video unavailable" in erro_lower or "this video is not available" in erro_lower:
        return (
            "ERRO: o YouTube informa que o vídeo não está disponível — pode "
            "ter sido removido ou bloqueado para a região/sessão atual. "
            "Confirme se o link abre normalmente no navegador. "
            f"Detalhe: {raw_error}"
        )

    if "sign in to confirm you" in erro_lower and "bot" in erro_lower:
        return (
            "ERRO ao baixar vídeo: o YouTube recusou a sessão por verificação "
            "anti-bot. Em servidor headless, valide Deno/EJS, COOKIES_FILE e "
            "PROXY_URL com `python -m tools.youtube_doctor`. "
            f"Diagnóstico: {_runtime_diag()}. Detalhe: {raw_error}"
        )

    # 403 durante transferência é diferente do bloqueio anti-bot da página.
    # Em 2026, formatos GVS de vários clients podem exigir PO Token.
    if "403" in erro_lower and (
        "forbidden" in erro_lower
        or "unable to download video data" in erro_lower
        or "http error 403" in erro_lower
    ):
        return (
            "ERRO ao baixar os dados do vídeo: o YouTube retornou HTTP 403 "
            "depois da extração. Esse padrão costuma ocorrer quando o formato "
            "GVS exige PO Token. Confirme no `python -m tools.youtube_doctor` "
            "que POT plugin/provider estão OK; o StudyFlow também tenta "
            "web_safari/HLS como fallback. "
            f"Diagnóstico: {_runtime_diag()}. Detalhe: {raw_error}"
        )

    return (
        "ERRO ao baixar vídeo. Pode ser bloqueio do YouTube, vídeo "
        "indisponível ou outro problema. Rode `python -m tools.youtube_doctor` "
        "e use o detalhe original abaixo para diagnóstico. Em servidor "
        "headless, prefira COOKIES_FILE; PROXY_URL trata reputação do IP e "
        "PO Token Provider trata enforcement GVS/403. "
        f"Detalhe: {raw_error}"
    )
