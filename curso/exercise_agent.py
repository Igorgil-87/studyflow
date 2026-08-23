"""
curso/exercise_agent.py — ExerciseAgent (Fase 5 do AI Course Generation
Engine, ver ai-course-engine-diagnostico.md, item 11 do pedido original:
"Exercícios Práticos — problemas, cenários, estudos de caso, perguntas
abertas, desafios... A IA deve avaliar a resposta considerando o
conteúdo do curso").

Duas funções, dois momentos diferentes:
  gerar_exercicio()  -> cria o enunciado (1x por aula, ou quantas vezes
                          o professor/aluno pedir "outro exercício")
  avaliar_resposta() -> avalia o que o ALUNO escreveu, contra o critério
                          e o conteúdo da aula — não é múltipla escolha,
                          é avaliação qualitativa por LLM
"""

from __future__ import annotations

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .curriculum_agent import COURSE_ENGINE_ANTHROPIC_MODEL, COURSE_ENGINE_OPENAI_MODEL

TIPOS_EXERCICIO = ["problema", "cenario", "estudo_de_caso", "pergunta_aberta", "desafio"]


class ExerciseAgentError(RuntimeError):
    """Erro ao gerar exercício ou avaliar resposta."""


class ExercicioDraft(BaseModel):
    tipo: str = Field(description=f"um de: {', '.join(TIPOS_EXERCICIO)}")
    enunciado: str = Field(description="O exercício em si — problema/cenário/pergunta, "
                                        "aplicando o conceito da aula numa situação concreta")
    resposta_esperada: str = Field(description="Os pontos-chave que uma boa resposta cobriria "
                                                "(não é gabarito literal — é critério)")
    avaliacao_criteria: str = Field(description="Como avaliar a resposta do aluno: o que "
                                                 "conta como completo, parcial, insuficiente")


class AvaliacaoDraft(BaseModel):
    nota_pct: int = Field(description="0 a 100 — o quanto a resposta do aluno cobre o critério", ge=0, le=100)
    feedback: str = Field(description="Feedback construtivo — o que a resposta acertou e o "
                                       "que faltou ou poderia melhorar")
    pontos_fortes: list[str] = Field(default_factory=list)
    pontos_a_melhorar: list[str] = Field(default_factory=list)


_SYSTEM_PROMPT_GERAR = """\
Você cria exercícios práticos pra um curso — não é quiz de múltipla escolha, é \
uma aplicação real do conceito. Exemplo do nível esperado: "Você precisa \
implementar RAG para 2 milhões de documentos. Como estruturaria essa \
arquitetura?" — não é "o que é RAG?".

Baseie o exercício SOMENTE no conteúdo da aula fornecido. Escolha o tipo mais \
adequado ao conteúdo (nem todo assunto vira "estudo de caso" — às vezes um \
"problema" objetivo é melhor). Responda em português brasileiro.
"""

_USER_TEMPLATE_GERAR = """\
AULA: {titulo}
CONTEÚDO:
{explicacao}

{format_instructions}
"""

_SYSTEM_PROMPT_AVALIAR = """\
Você avalia a resposta de um aluno a um exercício, considerando o conteúdo \
da aula — não é gabarito exato, é avaliação de COMPREENSÃO e APLICAÇÃO, não \
de memorização literal. Seja justo: uma resposta com palavras diferentes do \
"esperado" mas que demonstra entendimento correto merece nota alta. Seja \
específico no feedback — aponte exatamente o que faltou, não generalidades. \
Responda em português brasileiro.
"""

_USER_TEMPLATE_AVALIAR = """\
CONTEÚDO DA AULA (contexto):
{explicacao}

EXERCÍCIO:
{enunciado}

CRITÉRIO DE AVALIAÇÃO:
{avaliacao_criteria}

RESPOSTA DO ALUNO:
{resposta_aluno}

{format_instructions}
"""


def _build_chain_gerar():
    from tools.llm_fallback import build_llm_with_fallback

    parser = PydanticOutputParser(pydantic_object=ExercicioDraft)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PROMPT_GERAR),
        ("user", _USER_TEMPLATE_GERAR),
    ]).partial(format_instructions=parser.get_format_instructions())

    llm = build_llm_with_fallback(
        temperature=0.5, primary_provider="anthropic", primary_model=COURSE_ENGINE_ANTHROPIC_MODEL,
        fallback_provider="openai", fallback_model=COURSE_ENGINE_OPENAI_MODEL,
    )
    return prompt | llm | parser


def _build_chain_avaliar():
    from tools.llm_fallback import build_llm_with_fallback

    parser = PydanticOutputParser(pydantic_object=AvaliacaoDraft)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PROMPT_AVALIAR),
        ("user", _USER_TEMPLATE_AVALIAR),
    ]).partial(format_instructions=parser.get_format_instructions())

    llm = build_llm_with_fallback(
        temperature=0.2,  # avaliação: menos criatividade, mais consistência
        primary_provider="anthropic", primary_model=COURSE_ENGINE_ANTHROPIC_MODEL,
        fallback_provider="openai", fallback_model=COURSE_ENGINE_OPENAI_MODEL,
    )
    return prompt | llm | parser


def gerar_exercicio(titulo: str, explicacao: str) -> dict:
    if not explicacao or len(explicacao.strip()) < 50:
        raise ExerciseAgentError(
            "Conteúdo da aula insuficiente para gerar exercício — gere o "
            "conteúdo textual da aula primeiro."
        )
    chain = _build_chain_gerar()
    try:
        draft: ExercicioDraft = chain.invoke({"titulo": titulo, "explicacao": explicacao})
    except Exception as e:
        raise ExerciseAgentError(f"Falha ao gerar exercício: {e}") from e
    return draft.model_dump()


def avaliar_resposta(explicacao: str, enunciado: str, avaliacao_criteria: str, resposta_aluno: str) -> dict:
    if not resposta_aluno or not resposta_aluno.strip():
        raise ExerciseAgentError("Resposta vazia.")
    chain = _build_chain_avaliar()
    try:
        draft: AvaliacaoDraft = chain.invoke({
            "explicacao": explicacao, "enunciado": enunciado,
            "avaliacao_criteria": avaliacao_criteria, "resposta_aluno": resposta_aluno,
        })
    except Exception as e:
        raise ExerciseAgentError(f"Falha ao avaliar resposta: {e}") from e
    return draft.model_dump()
