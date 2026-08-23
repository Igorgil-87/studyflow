"""
tools/yt_error_classifier.py — traduz o erro cru do yt-dlp numa mensagem
que diz o que FAZER, sem chutar sempre a mesma explicação genérica.

Antes disso, TODO erro de download virava "o YouTube bloqueou o
download, atualize o yt-dlp ou configure cookies" — mesmo quando o
problema real era outra coisa (vídeo privado, removido, com restrição de
idade) onde essa orientação não ajuda nada.
"""

from __future__ import annotations


def classify_download_error(raw_error: str) -> str:
    """Recebe o texto cru de erro do yt-dlp (a última tentativa que
    falhou) e devolve uma mensagem explicando o problema REAL e o que
    fazer — não sempre a mesma sugestão genérica."""
    erro_lower = (raw_error or "").lower()

    if "private video" in erro_lower:
        return (
            "ERRO: esse vídeo está PRIVADO no YouTube — só quem tem acesso "
            "concedido à conta consegue baixar. Atualizar o yt-dlp não "
            "resolve isso (o vídeo não é público pra ninguém de fora). "
            "Se você TEM acesso, configure COOKIES_FILE no .env com um "
            "cookies.txt válido da conta que tenha esse acesso. Confirma também se o link "
            "está certo. "
            f"Detalhe: {raw_error}"
        )

    if "sign in to confirm your age" in erro_lower or ("age" in erro_lower and "restrict" in erro_lower):
        return (
            "ERRO: esse vídeo tem restrição de idade no YouTube. Configure "
            "COOKIES_FILE no .env com um cookies.txt de uma conta logada e "
            "maior de idade — sem isso, vídeo com restrição de idade pode não "
            "baixar de jeito nenhum, mesmo atualizando o yt-dlp. "
            f"Detalhe: {raw_error}"
        )

    if "video unavailable" in erro_lower or "this video is not available" in erro_lower:
        return (
            "ERRO: o YouTube diz que esse vídeo não está disponível — pode "
            "ter sido removido, ou estar bloqueado pra essa região. "
            "Confirma se o link abre normal no seu navegador antes de "
            "tentar de novo. "
            f"Detalhe: {raw_error}"
        )

    if "sign in to confirm you" in erro_lower and "bot" in erro_lower:
        try:
            from tools.youtube_runtime import runtime_status
            st = runtime_status()
            diag = (
                f"yt-dlp={st['yt_dlp']}; js_runtime={'ok' if st['js_runtime_ok'] else 'ausente'}; "
                f"cookies_file={'ok' if st['cookies_file_exists'] else 'ausente'}; "
                f"proxy={'on' if st['proxy_configured'] else 'off'}"
            )
        except Exception:
            diag = "diagnóstico local indisponível"
        return (
            "ERRO ao baixar vídeo: o YouTube recusou a sessão por verificação anti-bot. "
            "Em servidor headless, confirme primeiro o Deno/EJS com "
            "`python -m tools.youtube_doctor`; depois teste COOKIES_FILE. "
            "Se o IP de datacenter continuar bloqueado, configure PROXY_URL como fallback. "
            f"Diagnóstico: {diag}. Detalhe: {raw_error}"
        )

    # fallback — não sabemos classificar, mantém a orientação genérica
    # (mas sem fingir certeza sobre a causa)
    return (
        "ERRO ao baixar vídeo. Pode ser bloqueio do YouTube, vídeo "
        "indisponível, ou outro problema — o detalhe abaixo tem a causa "
        "exata reportada pelo yt-dlp. Se não for óbvio, tente atualizar o "
        "diagnóstico `python -m tools.youtube_doctor`; em servidor headless, "
        "prefira COOKIES_FILE e use PROXY_URL apenas quando necessário. "
        f"Detalhe: {raw_error}"
    )
