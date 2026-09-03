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

Quando usar um trecho do documento original, cite [Fonte N] exatamente como
identificado no contexto. Não invente páginas, slides ou fontes.
"""


class _GatewayLLMAdapter:
    """Adapter mínimo para preservar o contrato ``llm.invoke(messages)``.

    O Tutor continua testável do mesmo jeito, mas a implementação real passa
    pelo AI Gateway e ganha Gemini + fallback uniforme + tracing.
    """

    def invoke(self, messages):
        import os
        from types import SimpleNamespace
        from ai_gateway import generate_messages

        normalized = []
        for msg in messages:
            name = msg.__class__.__name__.lower()
            if "system" in name:
                role = "system"
            elif "ai" in name or "assistant" in name:
                role = "assistant"
            else:
                role = "user"
            normalized.append({"role": role, "content": str(getattr(msg, "content", msg))})

        result = generate_messages(
            normalized,
            preferred_provider=os.getenv("TUTOR_LLM_PROVIDER") or os.getenv("AI_PRIMARY_PROVIDER") or "anthropic",
            temperature=0.4,
            max_tokens=int(os.getenv("TUTOR_MAX_TOKENS", "2048")),
            operation="tutor_answer",
        )
        return SimpleNamespace(content=result.text, provider=result.provider, model=result.model)


def _montar_llm():
    import os
    if os.getenv("AI_GATEWAY_ENABLED", "1") != "0":
        return _GatewayLLMAdapter()

    # Compatibilidade de rollback: AI_GATEWAY_ENABLED=0 restaura o fallback
    # LangChain anterior sem mexer no restante do TutorAgent.
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

    if contexto_rag:
        try:
            from rag.query import _label_for_chunk
            trechos_rag = "\n\n".join(
                f"{_label_for_chunk(c, i)}\n{c['text']}" for i, c in enumerate(contexto_rag, start=1)
            )
        except Exception:
            trechos_rag = "\n\n".join(c["text"] for c in contexto_rag)
    else:
        trechos_rag = "(nenhum)"
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
