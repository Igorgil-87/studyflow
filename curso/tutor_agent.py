"""
curso/tutor_agent.py — TutorAgent (Fase 5 do AI Course Generation Engine,
ver ai-course-engine-diagnostico.md, seção "Fase 5 — Interatividade",
e item 12 do pedido original: "Pergunte ao Professor").

O aluno pergunta qualquer coisa sobre a aula atual. O tutor consulta:
  RAG (chunks do documento original, se o curso veio do Modo Criativo)
  + o conteúdo já gerado da aula (explicação)
  + o histórico da conversa (pra manter contexto entre perguntas)

Comandos naturais ("explique de forma mais simples", "dê um exemplo",
"explique como se eu tivesse 12 anos", "faça uma analogia", "me faça uma
pergunta pra ver se eu entendi" etc.) NÃO são tratados por um
classificador de intenção à parte — o system prompt instrui o modelo a
entender essas variações diretamente, é só mais uma pergunta em
linguagem natural. Isso evita duplicar lógica e é o comportamento mais
robusto (não quebra se o aluno pedir de um jeito que a lista não previu).
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .curriculum_agent import COURSE_ENGINE_ANTHROPIC_MODEL, COURSE_ENGINE_OPENAI_MODEL

MAX_HISTORICO_TURNOS = 10  # últimas N trocas — evita prompt crescer sem limite


class TutorAgentError(RuntimeError):
    """Erro ao responder a pergunta do aluno."""


_SYSTEM_PROMPT = """\
Você é o tutor de IA de um curso, respondendo dúvidas sobre a aula "{titulo_aula}".

Responda usando PRIORITARIAMENTE o material abaixo (conteúdo da aula + trechos \
do documento original, se houver). Se o aluno pedir uma explicação diferente \
("mais simples", "outro exemplo", "como se eu tivesse 12 anos", "uma analogia", \
"mais técnico", "compare com outra tecnologia"), atenda o pedido reformulando \
o MESMO conteúdo — não invente fato novo que não esteja no material.

Se o aluno pedir "me faça uma pergunta para ver se eu entendi", faça UMA \
pergunta objetiva sobre o conteúdo da aula (não responda por ele).

Se a pergunta for sobre algo que genuinamente não está no material, diga isso \
claramente antes de complementar com conhecimento geral — nunca misture as \
duas coisas sem avisar.

Responda em português brasileiro, direto e didático.

CONTEÚDO DA AULA:
{explicacao}

TRECHOS DO DOCUMENTO ORIGINAL (se disponíveis):
{contexto_rag}
"""


def _montar_llm():
    from tools.llm_fallback import build_llm_with_fallback
    return build_llm_with_fallback(
        temperature=0.4,
        primary_provider="anthropic",
        primary_model=COURSE_ENGINE_ANTHROPIC_MODEL,
        fallback_provider="openai",
        fallback_model=COURSE_ENGINE_OPENAI_MODEL,
    )


def perguntar(
    pergunta: str, titulo_aula: str, explicacao: str,
    contexto_rag: list[dict], historico: list[dict],
) -> str:
    """contexto_rag: chunks de curso/provenance.buscar_chunks_relevantes()
    (pode vir vazio). historico: lista de {"role": "aluno"|"tutor", "content": str},
    mais antigo primeiro — só as últimas MAX_HISTORICO_TURNOS entram no prompt."""
    if not pergunta or not pergunta.strip():
        raise TutorAgentError("Pergunta vazia.")
    if not explicacao or len(explicacao.strip()) < 20:
        raise TutorAgentError(
            "Esta aula ainda não tem conteúdo gerado — gere o conteúdo primeiro."
        )

    trechos_rag = "\n\n".join(c["text"] for c in contexto_rag) if contexto_rag else "(nenhum)"
    system = _SYSTEM_PROMPT.format(
        titulo_aula=titulo_aula, explicacao=explicacao, contexto_rag=trechos_rag,
    )

    mensagens = [SystemMessage(content=system)]
    for turno in historico[-MAX_HISTORICO_TURNOS:]:
        if turno["role"] == "aluno":
            mensagens.append(HumanMessage(content=turno["content"]))
        else:
            mensagens.append(AIMessage(content=turno["content"]))
    mensagens.append(HumanMessage(content=pergunta))

    llm = _montar_llm()
    try:
        resposta = llm.invoke(mensagens)
    except Exception as e:
        raise TutorAgentError(f"Falha ao consultar o tutor: {e}") from e

    return resposta.content if hasattr(resposta, "content") else str(resposta)
