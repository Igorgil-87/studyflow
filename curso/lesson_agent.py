"""
curso/lesson_agent.py — LessonContentAgent (Fase 1 do AI Course
Generation Engine, ver ai-course-engine-diagnostico.md).

Gera, POR AULA (não por curso inteiro), o conteúdo textual descrito no
item 5 do pedido: explicação didática completa, resumo rápido, e 3-7 key
takeaways. Reaproveita tools/quiz_generator.py pra quiz+flashcards da
mesma aula — só muda o escopo de "transcrição de vídeo inteiro" pra
"o material relevante desta aula".

Mesmo padrão de qualidade do CurriculumAgent (curso/curriculum_agent.py):
Claude no tier configurado em COURSE_ENGINE_MODEL por padrão, fallback pra
OpenAI só se a Anthropic falhar de verdade.
"""

from __future__ import annotations

import json
import os

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .curriculum_agent import COURSE_ENGINE_ANTHROPIC_MODEL, COURSE_ENGINE_OPENAI_MODEL

QUIZ_ANTHROPIC_MODEL = os.getenv("COURSE_ENGINE_QUIZ_MODEL", COURSE_ENGINE_ANTHROPIC_MODEL)


class LessonAgentError(RuntimeError):
    """Erro ao gerar conteúdo ou quiz de uma aula."""


class LessonContentDraft(BaseModel):
    explicacao: str = Field(description="Texto didático completo da aula, cobrindo o objetivo "
                                         "e os conceitos listados")
    resumo: str = Field(description="Resumo rápido, 2-4 frases")
    key_takeaways: list[str] = Field(
        description="Entre 3 e 7 conceitos essenciais que o aluno precisa lembrar",
        min_length=3, max_length=7,
    )


_SYSTEM_PROMPT = """\
Você é um professor especialista, escrevendo o material didático de UMA aula \
específica dentro de um curso maior. Use APENAS o material de referência \
fornecido — não invente fatos que não estejam nele. Se precisar complementar \
algo que o material não cobre, deixe isso implícito como conhecimento geral \
básico, sem apresentar como se viesse do material.

A explicação deve ENSINAR o conceito (com exemplo, se fizer sentido), não só \
descrever o que a aula "vai cobrir". Responda em português brasileiro.
"""

_USER_TEMPLATE = """\
AULA: {titulo}
OBJETIVO DE APRENDIZAGEM: {objetivo}
CONCEITOS A COBRIR: {conceitos}
ESTILO: {estilo}

MATERIAL DE REFERÊNCIA (trechos relevantes):
{material}

{format_instructions}
"""


def _build_chain():
    from tools.llm_fallback import build_llm_with_fallback

    parser = PydanticOutputParser(pydantic_object=LessonContentDraft)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PROMPT),
        ("user", _USER_TEMPLATE),
    ]).partial(format_instructions=parser.get_format_instructions())

    llm = build_llm_with_fallback(
        temperature=0.4,
        primary_provider="anthropic",
        primary_model=COURSE_ENGINE_ANTHROPIC_MODEL,
        fallback_provider="openai",
        fallback_model=COURSE_ENGINE_OPENAI_MODEL,
    )
    return prompt | llm | parser


def gerar_conteudo_aula(
    titulo: str, objetivo: str, conceitos: list[str], material: str, estilo: str = "pratico",
) -> dict:
    """Gera {explicacao, resumo, key_takeaways} pra UMA aula. Levanta
    LessonAgentError se os dois provedores de LLM falharem."""
    if not material or len(material.strip()) < 50:
        raise LessonAgentError(
            "Material de referência insuficiente para gerar o conteúdo desta aula."
        )
    chain = _build_chain()
    try:
        draft: LessonContentDraft = chain.invoke({
            "titulo": titulo,
            "objetivo": objetivo or "(infira a partir do título e do material)",
            "conceitos": ", ".join(conceitos) or "(infira a partir do material)",
            "estilo": estilo,
            "material": material,
        })
    except Exception as e:
        raise LessonAgentError(f"Falha ao gerar conteúdo da aula: {e}") from e
    return draft.model_dump()


def gerar_quiz_aula(
    titulo: str, texto_base: str, num_flashcards: int = 5, num_questions: int = 5,
) -> dict:
    """Quiz + flashcards de UMA aula, reaproveitando tools/quiz_generator.py
    (mesmo schema/parsing de sempre) — só muda o 'transcript' de entrada
    (vira o texto da explicação da aula, não o vídeo inteiro) e o provider
    (Claude, por pedido explícito de qualidade; a Opção 1/YouTube continua
    usando OpenAI, sem nenhuma mudança de comportamento)."""
    from tools.quiz_generator import QuizGeneratorTool

    tool = QuizGeneratorTool(
        llm_model=QUIZ_ANTHROPIC_MODEL, provider="anthropic",
        output_dir="output/quizzes_curso2",
    )
    resultado = tool._run(
        transcript=texto_base, topic=titulo,
        num_flashcards=num_flashcards, num_questions=num_questions,
    )
    if resultado.startswith("ERRO"):
        raise LessonAgentError(resultado)

    with open(resultado, encoding="utf-8") as f:
        return json.load(f)
