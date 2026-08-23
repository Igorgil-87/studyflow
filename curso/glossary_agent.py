"""
curso/glossary_agent.py — GlossaryAgent (Fase 2 do AI Course Generation
Engine, ver ai-course-engine-diagnostico.md, seção 9).

Gera definição curta pra cada conceito ÚNICO do curso, numa ÚNICA chamada
de LLM (não uma por conceito) — os conceitos já foram extraídos pelo
CurriculumAgent na Fase 1 e estão em curso/store.py::concepts, só falta
a definição. Mesmo padrão de qualidade dos outros agentes desta feature:
Claude por padrão, fallback OpenAI.
"""

from __future__ import annotations

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .curriculum_agent import COURSE_ENGINE_ANTHROPIC_MODEL, COURSE_ENGINE_OPENAI_MODEL


class GlossaryAgentError(RuntimeError):
    """Erro ao gerar o glossário do curso."""


class TermoGlossario(BaseModel):
    termo: str
    definicao: str = Field(description="Definição curta, 1-2 frases, no contexto deste curso")


class GlossarioDraft(BaseModel):
    termos: list[TermoGlossario]


_SYSTEM_PROMPT = """\
Você é um professor montando o glossário de um curso. Pra cada termo da lista, \
escreva uma definição curta (1-2 frases) e didática, no contexto específico \
deste curso — não uma definição de dicionário genérica. Responda em português \
brasileiro. Devolva EXATAMENTE um termo de saída pra cada termo de entrada, \
na mesma grafia.
"""

_USER_TEMPLATE = """\
CURSO: {titulo_curso}
DESCRIÇÃO: {descricao_curso}

TERMOS (defina cada um):
{termos}

{format_instructions}
"""


def _build_chain():
    from tools.llm_fallback import build_llm_with_fallback

    parser = PydanticOutputParser(pydantic_object=GlossarioDraft)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PROMPT),
        ("user", _USER_TEMPLATE),
    ]).partial(format_instructions=parser.get_format_instructions())

    llm = build_llm_with_fallback(
        temperature=0.3,
        primary_provider="anthropic",
        primary_model=COURSE_ENGINE_ANTHROPIC_MODEL,
        fallback_provider="openai",
        fallback_model=COURSE_ENGINE_OPENAI_MODEL,
    )
    return prompt | llm | parser


def gerar_glossario(titulo_curso: str, descricao_curso: str, conceitos: list[str]) -> dict[str, str]:
    """conceitos: lista de nomes únicos (curso/store.list dos concepts do
    curso). Retorna {termo: definicao}. Levanta GlossaryAgentError se os
    dois provedores falharem; lista vazia devolve {} sem chamar LLM."""
    if not conceitos:
        return {}
    chain = _build_chain()
    try:
        draft: GlossarioDraft = chain.invoke({
            "titulo_curso": titulo_curso,
            "descricao_curso": descricao_curso,
            "termos": "\n".join(f"- {c}" for c in conceitos),
        })
    except Exception as e:
        raise GlossaryAgentError(f"Falha ao gerar glossário: {e}") from e

    return {t.termo: t.definicao for t in draft.termos}
