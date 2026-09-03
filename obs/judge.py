"""
obs/judge.py — LLM-as-Judge: uma IA avalia a saída de outra.

Aqui, adaptado ao domínio real do projeto: avalia a qualidade de um QUIZ gerado
a partir do transcript de um vídeo. Não é o judge financeiro do ChamaAI — mede o
que importa aqui:

  - groundedness : as perguntas/respostas se sustentam no transcript?
  - relevance    : o quiz cobre o tema central do vídeo?
  - coherence    : enunciados e alternativas são claros e bem-formados?
  - hallucination: há afirmação inventada, fora do transcript?
  - judge_score  : nota consolidada 0..1

Tudo fail-open: se o juiz falhar, devolve veredito neutro e NUNCA derruba o
pipeline. A própria chamada do juiz é rastreada (custo do judge entra no FinOps).
"""

from __future__ import annotations

import json
import os

from . import db, pricing, tracing

JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini"))
MAX_CONTEXT_CHARS = int(os.getenv("EVAL_MAX_CONTEXT_CHARS", "6000"))

PROMPT_VERSION = os.getenv("EVAL_PROMPT_VERSION", "eval-v2")

_NEUTRAL = {
    "groundedness": None, "relevance": None, "coherence": None,
    "source_fidelity": None, "completeness": None,
    "hallucination": None, "judge_score": None,
    "rationale": "juiz indisponível (veredito neutro)", "ok": False,
}

_PROMPT = """Você é um avaliador rigoroso de qualidade de quizzes educacionais.
Avalie o QUIZ abaixo usando SOMENTE o TRANSCRIPT como verdade.

Responda APENAS com JSON válido, sem markdown, neste formato exato:
{{"groundedness":0..1,"relevance":0..1,"coherence":0..1,"hallucination":true/false,"judge_score":0..1,"rationale":"1 frase"}}

TRANSCRIPT:
{transcript}

QUIZ (JSON):
{quiz}
"""


_RESPONSE_PROMPT = """Você é um avaliador rigoroso de sistemas RAG e tutores educacionais.
Avalie a RESPOSTA usando SOMENTE o CONTEXTO como fonte factual e considerando a PERGUNTA.

Critérios (0..1):
- groundedness: quanto das afirmações factuais está sustentado pelo contexto.
- relevance: quanto a resposta atende diretamente à pergunta.
- coherence: clareza, consistência e organização.
- source_fidelity: fidelidade ao contexto, sem distorcer ou extrapolar o material.
- completeness: cobertura suficiente do que a pergunta exige, dentro do contexto disponível.
- hallucination: true se houver afirmação factual relevante não sustentada pelo contexto.
- judge_score: nota consolidada 0..1.

Responda APENAS JSON válido, sem markdown, neste formato exato:
{{"groundedness":0..1,"relevance":0..1,"coherence":0..1,"source_fidelity":0..1,"completeness":0..1,"hallucination":true/false,"judge_score":0..1,"rationale":"1 frase objetiva"}}

CONTEXTO:
{context}

PERGUNTA:
{question}

RESPOSTA:
{answer}
"""


def _default_caller(prompt: str, model: str) -> str:
    """Chamada real ao LLM via langchain (import tardio)."""
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model=model, temperature=0)
    return llm.invoke(prompt).content


def judge_quiz(
    transcript: str,
    quiz: dict,
    model: str | None = None,
    trace_id: str | None = None,
    _caller=None,
) -> dict:
    """Retorna o veredito (dict). Fail-open: nunca levanta exceção."""
    model = model or JUDGE_MODEL
    caller = _caller or _default_caller
    transcript = (transcript or "")[:MAX_CONTEXT_CHARS]
    prompt = _PROMPT.format(
        transcript=transcript,
        quiz=json.dumps(quiz, ensure_ascii=False)[:MAX_CONTEXT_CHARS],
    )

    # A chamada do juiz é rastreada e resiliente; fail-open para texto vazio.
    raw = tracing.traced_llm(
        "openai", "judge_quiz", model,
        caller, prompt, model,
        trace_id=trace_id, input_text=prompt, timeout=60, fallback="",
    )
    if not raw:
        return dict(_NEUTRAL)

    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`").lstrip("json").strip()
        data = json.loads(text)
        return {
            "groundedness": float(data.get("groundedness", 0)),
            "relevance": float(data.get("relevance", 0)),
            "coherence": float(data.get("coherence", 0)),
            "hallucination": bool(data.get("hallucination", False)),
            "judge_score": float(data.get("judge_score", 0)),
            "rationale": str(data.get("rationale", ""))[:500],
            "ok": True,
        }
    except Exception as e:
        out = dict(_NEUTRAL)
        out["rationale"] = f"parse falhou: {e}"
        return out


def judge_response(
    question: str, context: str, answer: str,
    model: str | None = None, trace_id: str | None = None, _caller=None,
) -> dict:
    """Avalia uma resposta grounded (RAG/tutor). Fail-open."""
    model = model or JUDGE_MODEL
    caller = _caller or _default_caller
    prompt = _RESPONSE_PROMPT.format(
        context=(context or "")[:MAX_CONTEXT_CHARS],
        question=(question or "")[:2000],
        answer=(answer or "")[:MAX_CONTEXT_CHARS],
    )
    raw = tracing.traced_llm(
        "openai", "judge_response", model, caller, prompt, model,
        trace_id=trace_id, input_text=prompt, timeout=60, fallback="",
    )
    if not raw:
        return dict(_NEUTRAL)
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`").lstrip("json").strip()
        data = json.loads(text)
        return {
            "groundedness": float(data.get("groundedness", 0)),
            "relevance": float(data.get("relevance", 0)),
            "coherence": float(data.get("coherence", 0)),
            "source_fidelity": float(data.get("source_fidelity", data.get("groundedness", 0))),
            "completeness": float(data.get("completeness", data.get("relevance", 0))),
            "hallucination": bool(data.get("hallucination", False)),
            "judge_score": float(data.get("judge_score", 0)),
            "rationale": str(data.get("rationale", ""))[:500],
            "ok": True,
        }
    except Exception as e:
        out = dict(_NEUTRAL)
        out["rationale"] = f"parse falhou: {e}"
        return out


def run_response_eval(
    trace_id: str, target: str, question: str, context: str, answer: str,
    model: str | None = None, _caller=None,
) -> dict:
    """Avalia uma resposta e persiste métricas comparáveis no dashboard."""
    verdict = judge_response(
        question, context, answer, model=model, trace_id=trace_id, _caller=_caller,
    )
    if verdict.get("ok"):
        db.insert_eval({
            "trace_id": trace_id, "target": target,
            "groundedness": verdict["groundedness"],
            "relevance": verdict["relevance"],
            "coherence": verdict["coherence"],
            "source_fidelity": verdict["source_fidelity"],
            "completeness": verdict["completeness"],
            "hallucination": verdict["hallucination"],
            "judge_score": verdict["judge_score"],
            "model": model or JUDGE_MODEL,
            "prompt_version": PROMPT_VERSION,
            "rationale": verdict["rationale"],
        })
    return verdict


def run_quiz_eval(
    trace_id: str, transcript: str, quiz: dict,
    model: str | None = None, _caller=None,
) -> dict:
    """Avalia e persiste o eval. Retorna o veredito."""
    verdict = judge_quiz(transcript, quiz, model=model,
                         trace_id=trace_id, _caller=_caller)
    if verdict.get("ok"):
        db.insert_eval({
            "trace_id": trace_id, "target": "quiz",
            "groundedness": verdict["groundedness"],
            "relevance": verdict["relevance"],
            "coherence": verdict["coherence"],
            "source_fidelity": verdict["groundedness"],
            "completeness": verdict["relevance"],
            "hallucination": verdict["hallucination"],
            "judge_score": verdict["judge_score"],
            "model": model or JUDGE_MODEL,
            "prompt_version": PROMPT_VERSION,
            "rationale": verdict["rationale"],
        })
    return verdict
