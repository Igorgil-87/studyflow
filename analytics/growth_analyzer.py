"""
analytics/growth_analyzer.py — aplica o framework de conteúdo viral (Hook-
Substance-Payoff, biblioteca de tipos de gancho, critérios de ideia viral,
táticas de engajamento) em cima de cada post REAL do perfil, cruzando com
a métrica de verdade — pra responder "por que esse viralizou e esse não".

Framework usado (baseado nas skills de growth/copywriting fornecidas):
  - Estrutura Hook-Substance-Payoff: gancho (5-7s) → substância (75-80%
    do conteúdo) → payoff (fecha o que o gancho prometeu)
  - Biblioteca de tipos de gancho: choque, parar-ação, economia de
    tempo/dinheiro, pergunta, antes/depois, erro/aviso, POV, números/listas
  - 4 critérios de ideia viral: relatable, provoca pergunta, provoca
    reação, parece irreal
  - Táticas de engajamento: controvérsia leve, erro proposital, CTA direto

IMPORTANTE — limitação honesta: pra posts HISTÓRICOS (origem='historico'),
só temos a legenda (caption) do post, não o vídeo/áudio em si — a análise
de gancho fica baseada no que a legenda sinaliza, não no vídeo real dos
primeiros 5-7s. Pra posts gerados pelo StudyFlow (origem='sistema'), o
hook real do vídeo já está salvo e entra na análise também, ficando mais
preciso.
"""

from __future__ import annotations

import json
import os

import anthropic

MODEL = os.getenv("CLAUDE_COPY_MODEL", "claude-haiku-4-5-20251001")

from tools.clip_rules import TIPOS_GANCHO


class GrowthAnalyzerError(RuntimeError):
    """Erro ao analisar um post."""


def is_alive() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


_SYSTEM = """Você analisa posts de Instagram usando um framework de conteúdo viral,
pra explicar objetivamente por que um post performou bem ou mal — nunca invente
métrica, só explique o padrão a partir do texto e dos números reais fornecidos.

FRAMEWORK — Hook-Substance-Payoff:
- Hook: os 5-7 segundos/primeira linha, precisa fazer parar de rolar
- Substance: 75-80% do conteúdo, entrega valor (educa e/ou entretém)
- Payoff: fecha a promessa do hook, é o motivo de salvar/compartilhar

TIPOS DE GANCHO (classifique em UM desses, pelo texto da legenda):
- choque: "não vai acreditar", revelação surpreendente
- parar_acao: "pare de fazer X"
- economia: promete economizar tempo/dinheiro
- pergunta: pergunta direta pro leitor
- antes_depois: mostra transformação
- erro_aviso: "5 erros que você comete"
- pov: formato "POV: ..."
- numeros_lista: "3 coisas que...", listas numeradas
- nenhum_claro: legenda não usa nenhum gancho reconhecível

4 CRITÉRIOS DE IDEIA VIRAL (avalie cada um como presente ou não, pelo texto):
- relatable: o tema se conecta com uma audiência ampla
- provoca_pergunta: faz o leitor pensar "como assim?"
- provoca_reacao: gera emoção (rir, surpresa, indignação)
- parece_irreal: soa quase bom/estranho demais pra ser verdade

TÁTICAS DE ENGAJAMENTO (liste as que aparecem):
- controversia_leve, erro_proposital, cta_direto

Responda APENAS com um JSON válido, sem texto antes/depois, no formato:
{"tipo_gancho": "...", "criterios_virais": {"relatable": true/false, "provoca_pergunta": true/false, "provoca_reacao": true/false, "parece_irreal": true/false}, "taticas_engajamento": ["..."], "tem_cta_claro": true/false, "resumo": "1-2 frases explicando o padrão, mencionando a métrica real dada"}"""


def analisar_publicacao(caption: str, hook: str | None, views: int | None,
                         likes: int | None) -> dict:
    """Manda UM post pro Claude analisar contra o framework. Retorna o
    dict pronto pra salvar via analytics.store.salvar_analise_ia()."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise GrowthAnalyzerError("ANTHROPIC_API_KEY não configurada no .env")
    if not caption and not hook:
        raise GrowthAnalyzerError("Post sem legenda e sem hook — nada pra analisar")

    partes = []
    if hook:
        partes.append(f"Hook do vídeo (real, dos primeiros segundos): {hook}")
    if caption:
        partes.append(f"Legenda do post: {caption}")
    partes.append(f"Métrica real: {views or 0} views, {likes or 0} likes")
    user_msg = "\n".join(partes)

    from tools.llm_fallback import call_with_fallback, LLMFallbackError
    try:
        raw = call_with_fallback(_SYSTEM, user_msg, max_tokens=600, anthropic_model=MODEL).strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
        analise = json.loads(raw)
    except (json.JSONDecodeError, LLMFallbackError) as e:
        raise GrowthAnalyzerError(f"Falha ao analisar post: {e}") from e

    if analise.get("tipo_gancho") not in TIPOS_GANCHO:
        analise["tipo_gancho"] = "nenhum_claro"

    return analise


_SYSTEM_RECOMENDACOES = """Você é um estrategista de crescimento de Instagram. Recebe um
resumo REAL de performance por tipo de gancho (dados agregados de posts de verdade) e os
melhores/piores posts reais com a análise de cada um — sua tarefa é sintetizar isso em
recomendações CONCRETAS e ACIONÁVEIS pro PRÓXIMO conteúdo.

Regras:
- NUNCA dê conselho genérico de mercado ("use ganchos fortes", "poste mais"). Toda
  recomendação precisa citar o PADRÃO REAL encontrado nos dados (ex: "seus posts com
  gancho de choque tiveram em média 3x mais views que os de pergunta — use esse tipo
  no próximo vídeo sobre X").
- Se os dados forem poucos (menos de 5 posts analisados), diga isso explicitamente e
  recomende sincronizar/analisar mais posts antes de confiar demais no padrão.
- Máximo 5 recomendações, cada uma em 1-2 frases, específica e testável.

Responda APENAS com um JSON válido: {"recomendacoes": ["...", "...", ...], "confianca": "baixa"|"media"|"alta", "motivo_confianca": "1 frase"}"""


def gerar_recomendacoes(por_gancho: list[dict], top_posts: list[dict]) -> dict:
    """Sintetiza o resumo agregado (analytics.store.resumo_por_gancho) +
    os melhores posts reais (analytics.store.top_publicacoes_reais) em
    recomendações concretas pro próximo conteúdo."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise GrowthAnalyzerError("ANTHROPIC_API_KEY não configurada no .env")

    total_analisados = sum(g.get("n", 0) for g in por_gancho)
    if total_analisados == 0:
        return {
            "recomendacoes": [],
            "confianca": "baixa",
            "motivo_confianca": "Nenhum post analisado ainda — sincroniza o perfil e roda a análise de padrões primeiro.",
        }

    partes = ["RESUMO POR TIPO DE GANCHO (dados reais):"]
    for g in por_gancho:
        partes.append(f"- {g['tipo_gancho']}: {g['n']} post(s), média de {g['media_views']:.0f} views")

    partes.append("\nMELHORES POSTS REAIS (com a análise de cada um):")
    for p in top_posts[:5]:
        analise = p.get("analise_ia") or {}
        partes.append(
            f"- \"{(p.get('caption') or p.get('titulo') or '')[:80]}\" — "
            f"{p.get('views')} views, gancho={analise.get('tipo_gancho', '?')}, "
            f"resumo: {analise.get('resumo', 'sem análise')}"
        )

    user_msg = "\n".join(partes)

    from tools.llm_fallback import call_with_fallback, LLMFallbackError
    try:
        raw = call_with_fallback(_SYSTEM_RECOMENDACOES, user_msg, max_tokens=1000,
                                  anthropic_model=MODEL).strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except (json.JSONDecodeError, LLMFallbackError) as e:
        raise GrowthAnalyzerError(f"Falha ao gerar recomendações: {e}") from e


def analisar_pendentes(plataforma: str | None = None, limit: int = 20) -> dict:
    """Roda em lote: pega posts com métrica real mas sem análise ainda,
    analisa cada um, salva. Mesmo padrão dos outros fetchers em lote."""
    from analytics.store import list_sem_analise, salvar_analise_ia

    pendentes = list_sem_analise(plataforma=plataforma, limit=limit)
    if not pendentes:
        return {"processadas": 0, "ok": 0, "falhas": 0, "detalhes": []}

    ok, falhas, detalhes = 0, 0, []
    for pub in pendentes:
        try:
            analise = analisar_publicacao(
                pub.get("caption", ""), pub.get("hook"), pub.get("views"), pub.get("likes"))
            salvar_analise_ia(pub["id"], analise)
            ok += 1
            detalhes.append({"id": pub["id"], "status": "ok", "tipo_gancho": analise.get("tipo_gancho")})
        except Exception as e:
            falhas += 1
            detalhes.append({"id": pub["id"], "status": "erro", "erro": str(e)})

    return {"processadas": len(pendentes), "ok": ok, "falhas": falhas, "detalhes": detalhes}
