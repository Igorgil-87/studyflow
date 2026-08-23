"""
curso/storyboard_agent.py — StoryboardAgent (Fase 3 do AI Course
Generation Engine, ver ai-course-engine-diagnostico.md, seção 8).

Entrada: o conteúdo textual já gerado pela aula (Fase 1 —
LessonContentAgent). Saída: um storyboard — lista de cenas, cada uma com
narração, descrição visual, duração estimada e referência de fonte (pra
manter o provenance também no vídeo, não só no texto).

NÃO gera vídeo nem áudio — só a estrutura. Quem renderiza é
curso/video_render.py. Mesmo padrão de qualidade dos outros agentes:
Claude por padrão, fallback OpenAI.
"""

from __future__ import annotations

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from .curriculum_agent import COURSE_ENGINE_ANTHROPIC_MODEL, COURSE_ENGINE_OPENAI_MODEL

# Tipos de cena suportados pelo renderer (curso/video_render.py). "diagrama"
# é totalmente determinístico (Pillow, sem custo extra de IA de imagem) —
# cobre a maioria dos pedidos (conceito destacado, lista, comparação,
# definição). "footage" fica reservado pro VideoRenderAgent decidir usar
# tools/mpt_client.py quando isso for ligado (ver nota em video_render.py:
# ainda não integrado nesta primeira versão da Fase 3).
TIPOS_CENA = ["diagrama", "footage"]


class StoryboardAgentError(RuntimeError):
    """Erro ao gerar o storyboard de uma aula."""


class Cena(BaseModel):
    tipo: str = Field(description=f"um de: {', '.join(TIPOS_CENA)}")
    narration: str = Field(description="Texto que será narrado nesta cena (TTS)")
    visual_description: str = Field(
        description="O que aparece na tela: título curto + até 5 pontos-chave "
                     "(bullet points) que resumem o que está sendo narrado"
    )
    duration_seconds: int = Field(description="Duração estimada da cena, baseada no "
                                                "tamanho da narração (~2.5 palavras/segundo)")
    source_reference: str = Field(default="", description="De qual key takeaway ou "
                                                            "trecho da explicação esta cena vem")


class StoryboardDraft(BaseModel):
    scenes: list[Cena] = Field(min_length=1, max_length=12)


_SYSTEM_PROMPT = """\
Você é um roteirista de vídeos educacionais. Transforme o conteúdo da aula \
abaixo em um STORYBOARD — uma sequência de cenas curtas, cada uma cobrindo \
UM ponto por vez. Não é slide estático de texto corrido: cada cena tem uma \
narração falada (natural, como um professor explicando) e uma descrição \
visual OBJETIVA (título + poucos bullet points, nunca um parágrafo).

Regras:
1. Entre 3 e 8 cenas — nem uma cena gigante, nem uma cena por frase.
2. A soma das durações deve bater aproximadamente com o tamanho do texto \
original (não invente conteúdo novo além do fornecido).
3. Toda cena tipo "diagrama" deve ter visual_description com título curto \
+ até 5 bullets (nunca frases longas — é o que vai aparecer NA TELA).
4. Use tipo "footage" só quando o conteúdo pedir claramente um exemplo do \
mundo real (não é o padrão — a maioria das cenas deve ser "diagrama").
5. Responda em português brasileiro.
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

    parser = PydanticOutputParser(pydantic_object=StoryboardDraft)
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


def gerar_storyboard(titulo: str, explicacao: str, key_takeaways: list[str]) -> dict:
    """Retorna {"scenes": [...]}, pronto pra persistir e renderizar."""
    if not explicacao or len(explicacao.strip()) < 50:
        raise StoryboardAgentError(
            "Conteúdo da aula insuficiente para montar storyboard — gere o "
            "conteúdo textual da aula primeiro."
        )
    chain = _build_chain()
    try:
        draft: StoryboardDraft = chain.invoke({
            "titulo": titulo,
            "explicacao": explicacao,
            "key_takeaways": ", ".join(key_takeaways),
        })
    except Exception as e:
        raise StoryboardAgentError(f"Falha ao gerar storyboard: {e}") from e
    return draft.model_dump()
