"""
tools/claude_copy_client.py — usa a API da Anthropic (Claude) pra escrever
o texto de cada slide do carrossel: um "kicker" curto, uma headline forte
(o gancho que precisa parar o scroll) e um footer de apoio.

Por que existir: pedir pra IA de IMAGEM desenhar o texto dentro da própria
imagem sempre sai ruim (letras deformadas, palavras erradas) — é uma
limitação conhecida de todo modelo de geração de imagem, não só um motor
específico. A solução profissional é separar as duas coisas: a IA de
imagem gera só o fundo/ilustração (sem texto), e o texto é escrito por um
LLM de texto (Claude, aqui) e depois aplicado com tipografia de verdade
via tools/carousel_composer.py — sempre nítido, sempre legível.

Credenciais (.env):
    ANTHROPIC_API_KEY

Modelo: claude-haiku-4-5-20251001 por padrão — rápido e barato o
suficiente pra copy curta; troque via CLAUDE_COPY_MODEL se quiser mais
qualidade (ex: um Sonnet).
"""

from __future__ import annotations

import json
import os

import anthropic

from .anti_slop import ANTI_SLOP_RULES

MODEL = os.getenv("CLAUDE_COPY_MODEL", "claude-haiku-4-5-20251001")

_SYSTEM_PROMPT = """Você escreve o texto de carrosséis de Instagram sobre \
Cloud, IA e engenharia de plataforma, no estilo de criadores de conteúdo \
tech que realmente prendem atenção (frases curtas, diretas, com um \
"gancho" que gera identificação ou choque de realidade — nunca clickbait \
falso ou sensacionalista, sempre baseado em algo tecnicamente verdadeiro).

Regras:
- Português do Brasil, tom direto, sem enrolação.
- "kicker": 2-4 palavras, MAIÚSCULAS, contexto do slide (ex: "RIGHTSIZING").
- "headline": a frase principal do slide, curta o suficiente pra ficar \
grande na tela (idealmente até ~9 palavras). É o que precisa parar o \
scroll.
- "footer": 1 frase de apoio/explicação, pode ser um pouco mais longa.
- No ÚLTIMO slide, o footer deve ter uma chamada de ação clara (comentar \
uma palavra-chave, seguir, salvar).

""" + ANTI_SLOP_RULES + """
- Responda APENAS com um JSON válido: uma lista de objetos com as chaves \
"kicker", "headline", "footer". Nada de texto antes ou depois."""


class ClaudeCopyError(RuntimeError):
    """Erro ao gerar o texto do carrossel via Claude."""


def is_alive() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def generate_carousel_copy(
    pilar: str,
    topic: str,
    slide_count: int = 6,
    rag_context: str = "",
) -> list[dict]:
    """Gera o texto (kicker/headline/footer) de cada slide do carrossel.

    pilar: um dos 12 pilares de conteúdo (ex: "FinOps", "Cloud Native")
    topic: o ângulo específico dentro do pilar (ex: "rightsizing, \
autoscaling, spot instances e savings plans")
    slide_count: quantos slides o carrossel vai ter (2 a 10)
    rag_context: trechos relevantes já indexados na base vetorial do
        projeto (vídeos transcritos, tendências) — se vier preenchido, o
        Claude usa isso como referência real em vez de só conhecimento
        genérico (ver tools/rag_context.py)

    Retorna uma lista de dicts: [{"kicker", "headline", "footer"}, ...]
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ClaudeCopyError("ANTHROPIC_API_KEY não configurada no .env")
    if not (2 <= slide_count <= 10):
        raise ClaudeCopyError("slide_count precisa estar entre 2 e 10")

    user_msg = (
        f"Pilar: {pilar}\n"
        f"Tema/ângulo deste post: {topic}\n"
        f"Gere exatamente {slide_count} slides."
    )
    if rag_context:
        user_msg += (
            "\n\nContexto real já indexado da base de conhecimento do "
            "projeto (vídeos/tendências que você já cobriu) — use isso "
            "pra dar exemplos e afirmações específicas, não genéricas, "
            "quando fizer sentido:\n" + rag_context
        )
    from tools.llm_fallback import call_with_fallback, LLMFallbackError
    try:
        raw_text = call_with_fallback(
            _SYSTEM_PROMPT, user_msg, max_tokens=1200, anthropic_model=MODEL
        ).strip()
    except LLMFallbackError as exc:
        raise ClaudeCopyError(f"Falha ao gerar copy: {exc}") from exc

    # Claude às vezes envolve o JSON em ```json ... ``` mesmo quando
    # instruído a não fazer isso — remove se vier assim.
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        slides = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ClaudeCopyError(
            f"Claude não retornou um JSON válido: {raw_text[:300]}"
        ) from exc

    if not isinstance(slides, list) or len(slides) != slide_count:
        raise ClaudeCopyError(
            f"Esperava {slide_count} slides, Claude retornou: {str(slides)[:300]}"
        )
    for s in slides:
        if not all(k in s for k in ("kicker", "headline", "footer")):
            raise ClaudeCopyError(f"Slide sem os 3 campos esperados: {s}")

    return slides


def generate_caption(pilar: str, topic: str, slides_copy: list[dict]) -> str:
    """Gera a legenda do POST (não do slide) a partir do texto que já
    saiu de generate_carousel_copy — pra fechar o ciclo "gerar → publicar"
    sem o usuário precisar escrever nada na mão. Retorna 2-4 linhas +
    hashtags, pronta pra colar direto no campo de legenda do Instagram."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ClaudeCopyError("ANTHROPIC_API_KEY não configurada no .env")

    slides_text = "\n".join(
        f"- {s['kicker']}: {s['headline']}" for s in slides_copy
    )
    system = (
        "Você escreve a legenda de posts de Instagram sobre Cloud/IA/"
        "engenharia, curta e direta, no mesmo tom do carrossel. Regras: "
        "2 a 4 linhas de texto (pode ter quebra de linha), termina com uma "
        "chamada de ação simples (comentar, salvar ou seguir), e 4-6 "
        "hashtags relevantes no final, em português.\n\n"
        + ANTI_SLOP_RULES +
        "\nResponda só com a legenda pronta — nada de explicação, aspas ou markdown."
    )
    user = f"Pilar: {pilar}\nTema: {topic}\nSlides do carrossel:\n{slides_text}"
    from tools.llm_fallback import call_with_fallback, LLMFallbackError
    try:
        return call_with_fallback(system, user, max_tokens=400, anthropic_model=MODEL).strip()
    except LLMFallbackError as exc:
        raise ClaudeCopyError(f"Falha ao gerar legenda: {exc}") from exc
