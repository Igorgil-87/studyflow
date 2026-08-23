"""
curso/podcast_agent.py — PodcastAgent (Fase 4 do AI Course Generation
Engine, ver ai-course-engine-diagnostico.md, seção 9 + item 7 do pedido
original: "o mesmo conteúdo pode ser transformado em uma conversa
didática entre dois participantes").

Entrada: o conteúdo textual da aula (Fase 1). Saída: um roteiro de
diálogo entre dois apresentadores (A pergunta/provoca, B explica —
padrão clássico de podcast educacional), grounded no texto original —
não pode inventar fato novo, só reformular em conversa.
"""

from __future__ import annotations

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .curriculum_agent import COURSE_ENGINE_ANTHROPIC_MODEL, COURSE_ENGINE_OPENAI_MODEL


class PodcastAgentError(RuntimeError):
    """Erro ao gerar o roteiro do podcast."""


class Fala(BaseModel):
    speaker: str = Field(description='"A" ou "B"')
    text: str = Field(description="O que este apresentador fala neste turno")


class PodcastScript(BaseModel):
    turns: list[Fala] = Field(min_length=6, max_length=30)


_SYSTEM_PROMPT = """\
Você é roteirista de um podcast educacional com DOIS apresentadores:
- Apresentador A: guia a conversa, faz perguntas, provoca curiosidade, resume.
- Apresentador B: é o especialista, explica os conceitos com profundidade.

Transforme o conteúdo da aula abaixo numa conversa NATURAL entre os dois —
não é o texto original lido em voz alta, é uma DISCUSSÃO sobre o assunto. \
B pode usar analogias e exemplos, mas o conteúdo factual precisa continuar \
fundamentado no texto original (não invente fato novo que não esteja lá). \
Alterne bastante entre A e B (turnos curtos, como conversa de verdade, não \
monólogos). Responda em português brasileiro.
"""

_USER_TEMPLATE = """\
AULA: {titulo}
EXPLICAÇÃO COMPLETA:
{explicacao}

KEY TAKEAWAYS: {key_takeaways}

{format_instructions}
"""


def _build_chain():
    from tools.llm_fallback import build_llm_with_fallback

    parser = PydanticOutputParser(pydantic_object=PodcastScript)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PROMPT),
        ("user", _USER_TEMPLATE),
    ]).partial(format_instructions=parser.get_format_instructions())

    llm = build_llm_with_fallback(
        temperature=0.5,
        primary_provider="anthropic",
        primary_model=COURSE_ENGINE_ANTHROPIC_MODEL,
        fallback_provider="openai",
        fallback_model=COURSE_ENGINE_OPENAI_MODEL,
    )
    return prompt | llm | parser


def gerar_podcast_script(titulo: str, explicacao: str, key_takeaways: list[str]) -> dict:
    """Retorna {"turns": [{"speaker": "A"|"B", "text": ...}, ...]}."""
    if not explicacao or len(explicacao.strip()) < 50:
        raise PodcastAgentError(
            "Conteúdo da aula insuficiente para montar o roteiro do podcast — "
            "gere o conteúdo textual da aula primeiro."
        )
    chain = _build_chain()
    try:
        draft: PodcastScript = chain.invoke({
            "titulo": titulo,
            "explicacao": explicacao,
            "key_takeaways": ", ".join(key_takeaways),
        })
    except Exception as e:
        raise PodcastAgentError(f"Falha ao gerar roteiro do podcast: {e}") from e

    turns = draft.model_dump()["turns"]
    invalidos = [t for t in turns if t["speaker"] not in ("A", "B")]
    if invalidos:
        raise PodcastAgentError(
            f"O modelo devolveu speaker inválido (só 'A' ou 'B' são aceitos): {invalidos[0]}"
        )
    return {"turns": turns}
