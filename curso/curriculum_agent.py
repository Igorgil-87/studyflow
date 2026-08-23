"""
curso/curriculum_agent.py — CurriculumAgent (Fase 1 do AI Course
Generation Engine, ver ai-course-engine-diagnostico.md).

Analisa o material de entrada (transcrição de vídeo — Opção 1, ou chunks
do RAG a partir de documento — Opção 2) e monta o Course Manifest: módulos
→ aulas → objetivos → conceitos, com pré-requisitos e lacunas identificadas.

Modelo: por pedido explícito do usuário ("sempre priorize melhor
qualidade"), usa o tier de maior qualidade da Anthropic por padrão —
já integrada no projeto (tools/llm_fallback.py, langchain-anthropic no
requirements.txt), sem precisar de fornecedor novo. Cai pra OpenAI gpt-4o
(não o -mini, pra não perder qualidade na queda) só se a Anthropic falhar
de verdade (erro de API/rede, não erro de conteúdo).

Isso é DELIBERADAMENTE separado de tools/roadmap_generator.py: aquele
continua servindo a Opção 1 (YouTube) exatamente como hoje, sem mudança
nenhuma. Este agente é mais rico (grafo de pré-requisito, lacunas,
conceitos repetidos) e monta o schema completo do Course Manifest —
os dois convergem no MESMO formato de manifest via
`curriculum_agent.manifest_from_roadmap()` pra Opção 1 não perder a
camada de persistência nova (curso/store.py).
"""

from __future__ import annotations

import json
import os

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

# Tier de qualidade máxima por padrão — troque via .env se quiser reduzir
# custo; nunca cai pra um tier mais barato sozinho.
COURSE_ENGINE_ANTHROPIC_MODEL = os.getenv("COURSE_ENGINE_MODEL", "claude-opus-4-8")
COURSE_ENGINE_OPENAI_MODEL = os.getenv("COURSE_ENGINE_FALLBACK_MODEL", "gpt-4o")

PUBLICOS = ["iniciante", "estudante", "desenvolvedor", "arquiteto", "executivo", "especialista"]
NIVEIS = ["introducao", "fundamentos", "intermediario", "avancado", "deep_dive"]
ESTILOS = ["academico", "executivo", "professor", "tecnico", "pratico", "storytelling"]


class CurriculumAgentError(RuntimeError):
    """Erro ao gerar o Course Manifest."""


# ── Schema de saída (Pydantic → JSON estruturado, mesmo padrão de
#    tools/quiz_generator.py e tools/roadmap_generator.py) ──────────────────

class LessonSpec(BaseModel):
    title: str
    objective: str
    duration_min: int = Field(description="Duração estimada da aula em minutos")
    concepts: list[str] = Field(description="Nomes dos conceitos cobertos nesta aula")
    video_required: bool = True
    audio_required: bool = True
    quiz_required: bool = True
    exercise_required: bool = False


class ModuleSpec(BaseModel):
    title: str
    objective: str
    lessons: list[LessonSpec]


class KnowledgeGap(BaseModel):
    descricao: str = Field(description="Lacuna identificada no material, ex: "
                                        "'o documento explica RAG mas não embeddings'")
    conceito_faltante: str


class CourseManifestDraft(BaseModel):
    """Saída do LLM. course_id/status são preenchidos depois por
    curso/store.py — o LLM não decide isso."""
    title: str
    description: str
    audience: str = Field(description=f"um de: {', '.join(PUBLICOS)}")
    difficulty: str = Field(description=f"um de: {', '.join(NIVEIS)}")
    estimated_duration_min: int
    style: str = Field(description=f"um de: {', '.join(ESTILOS)}")
    learning_objectives: list[str]
    prerequisites: list[str]
    modules: list[ModuleSpec]
    knowledge_gaps: list[KnowledgeGap] = Field(default_factory=list)


_SYSTEM_PROMPT = """\
Você é um curriculum designer especialista. Sua tarefa é analisar o material \
fornecido e estruturar um curso pedagogicamente sólido — não é um resumo, é uma \
TRANSFORMAÇÃO do material em experiência de aprendizagem.

Regras obrigatórias:
1. Identifique conceitos principais, secundários, e a DEPENDÊNCIA entre eles \
(o que precisa vir antes do quê). Organize os módulos do mais simples pro mais \
complexo, respeitando essas dependências.
2. Evite aulas redundantes — se dois trechos do material cobrem o mesmo conceito, \
uma única aula cobre os dois, não duplique.
3. Cada aula precisa de um objetivo de aprendizagem claro e específico (não \
"aprender sobre X", e sim o que o aluno consegue FAZER depois da aula).
4. Se o material tiver lacuna (menciona um conceito necessário mas não explica), \
liste em knowledge_gaps — não invente conteúdo pra preencher a lacuna silenciosamente.
5. Adeque profundidade e linguagem ao público e nível pedidos.
6. audience, difficulty e style DEVEM ser exatamente um dos valores permitidos \
listados no schema — não invente uma variação.
"""

_USER_TEMPLATE = """\
MATERIAL DE ORIGEM:
{material}

CONFIGURAÇÃO DESEJADA:
- Nome sugerido (pode ajustar): {nome_sugerido}
- Objetivo do curso: {objetivo}
- Público: {publico}
- Nível: {nivel}
- Duração desejada total: {duracao_min} minutos
- Estilo: {estilo}

{format_instructions}
"""


def _build_chain():
    from tools.llm_fallback import build_llm_with_fallback

    parser = PydanticOutputParser(pydantic_object=CourseManifestDraft)
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


def gerar_manifesto(
    material: str,
    *,
    nome_sugerido: str = "",
    objetivo: str = "",
    publico: str = "estudante",
    nivel: str = "fundamentos",
    duracao_min: int = 60,
    estilo: str = "pratico",
) -> dict:
    """Gera o Course Manifest (dict, pronto pra curso/store.criar_curso).
    Levanta CurriculumAgentError se o material for vazio demais ou os dois
    provedores de LLM falharem."""
    if not material or len(material.strip()) < 200:
        raise CurriculumAgentError(
            "Material insuficiente para gerar um curso (mínimo ~200 caracteres "
            "de conteúdo útil extraído)."
        )
    if publico not in PUBLICOS:
        publico = "estudante"
    if nivel not in NIVEIS:
        nivel = "fundamentos"
    if estilo not in ESTILOS:
        estilo = "pratico"

    chain = _build_chain()
    try:
        draft: CourseManifestDraft = chain.invoke({
            "material": material,
            "nome_sugerido": nome_sugerido or "(sugira um título)",
            "objetivo": objetivo or "(infira a partir do material)",
            "publico": publico,
            "nivel": nivel,
            "duracao_min": duracao_min,
            "estilo": estilo,
        })
    except Exception as e:
        raise CurriculumAgentError(f"Falha ao gerar manifesto: {e}") from e

    manifest = draft.model_dump()
    manifest["status"] = "aguardando_aprovacao"
    return manifest


def manifest_from_roadmap(roadmap_data: dict, topic: str) -> dict:
    """Converte a saída de tools/roadmap_generator.py (Opção 1 · YouTube,
    fluxo INTOCADO) pro mesmo formato de Course Manifest, só pra ganhar a
    camada de persistência nova (curso/store.py) sem re-gerar nada com
    LLM de novo — zero custo extra, é só reformatar o que o roadmap já
    calculou."""
    modulos = []
    for m in roadmap_data.get("modulos", []):
        modulos.append({
            "title": m.get("titulo", ""),
            "objective": m.get("objetivo", ""),
            "lessons": [{
                "title": m.get("titulo", ""),
                "objective": m.get("objetivo", ""),
                "duration_min": _parse_duracao(m.get("duracao_estimada", "")),
                "concepts": m.get("topicos", []),
                "video_required": True,
                "audio_required": False,
                "quiz_required": True,
                "exercise_required": False,
            }],
        })
    return {
        "title": topic,
        "description": roadmap_data.get("resumo", ""),
        "audience": "estudante",
        "difficulty": {"iniciante": "fundamentos", "intermediário": "intermediario",
                        "avançado": "avancado"}.get(roadmap_data.get("nivel", ""), "fundamentos"),
        "estimated_duration_min": sum(_parse_duracao(m.get("duracao_estimada", ""))
                                       for m in roadmap_data.get("modulos", [])),
        "style": "pratico",
        "learning_objectives": [roadmap_data.get("resumo", "")] if roadmap_data.get("resumo") else [],
        "prerequisites": roadmap_data.get("pre_requisitos", []),
        "modules": modulos,
        "knowledge_gaps": [],
        "status": "aguardando_aprovacao",
    }


def _parse_duracao(texto: str) -> int:
    """'30 min' -> 30, '1h' -> 60 — fail-open pra 15 se não conseguir parsear."""
    import re
    m = re.search(r"(\d+)\s*h", texto, re.IGNORECASE)
    if m:
        return int(m.group(1)) * 60
    m = re.search(r"(\d+)", texto)
    return int(m.group(1)) if m else 15
