"""
tools/highlight_extractor.py
Analisa transcrição com timestamps e identifica os momentos mais
virais/impactantes para Shorts, Reels, cortes médios ou longos.
"""

import json
import os
from pathlib import Path
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from .clip_rules import CONTENT_CONFIGS as _CONTENT_CONFIGS
from .clip_rules import clip_bounds, get_config, resolve_qty  # noqa: F401
from .clip_rules import build_transcript_view
from .clip_rules import TIPOS_GANCHO as _TIPOS_GANCHO
from .anti_slop import ANTI_SLOP_RULES

_TIPOS = (
    "hook | insight | momento_emocional | "
    "demonstracao | controversia | cta"
)


class Highlight(BaseModel):
    titulo: str = Field(default="Clip sem título", description="MELHOR título viral em PT-BR (máx 60 chars)")
    titulos_alt: list[str] = Field(
        default_factory=list,
        description=("10 títulos virais alternativos em PT-BR. Use padrões como: "
                     "'A Verdade Sobre...', 'Historiadores Não Conseguem Explicar...', "
                     "'O Que Realmente Aconteceu...', 'O Segredo Por Trás De...', "
                     "'Ninguém Esperava...', 'Cientistas Descobriram...', "
                     "'O Mistério De...', 'Por Que...', 'A História Não Contada De...', "
                     "'A Verdade Sombria Sobre...'. Sem clickbait sem lastro."))
    inicio: float = Field(description="Tempo de início em segundos")
    fim: float = Field(description="Tempo de fim em segundos")
    tipo: str = Field(default="insight", description=f"Tipo: {_TIPOS}")
    viral_score: int = Field(default=0, description="VIRAL SCORE total de 0 a 100")
    tier: str = Field(default="B", description="Tier: S (1M+), A (500k+), B (100k+) ou C (médio)")
    motivo: str = Field(default="", description="Por que pode viralizar (1-2 frases)")
    hook: str = Field(default="", description="Gancho ORIGINAL: frase/ação exata dos 3 primeiros segundos")
    hook_otimizado: str = Field(
        default="",
        description=(
            "Gancho OTIMIZADO pros 3 primeiros segundos, mais forte que o original. "
            "NUNCA começa com saudação/introdução ('e aí pessoal', 'nesse vídeo') — "
            "isso é 'limpar a garganta', o assassino nº1 de retenção. Estrutura em "
            "3 passos: (1) situação que o espectador reconhece/deseja, rápida; "
            "(2) uma virada inesperada que quebra o piloto automático; (3) por que "
            "ESSE vídeo é diferente de todos os outros sobre o tema. Começa no meio "
            "da ação, não com contexto."))
    hashtags: list[str] = Field(default_factory=list, description="5-8 hashtags sem #")
    descricao: str = Field(
        default="",
        description=("Descrição do YouTube (PT-BR), 2 a 4 frases. Varia a "
                     "estrutura de clip pra clip — não repete sempre a mesma "
                     "fórmula de 'gancho + valor + CTA + hashtags' na mesma "
                     "ordem, isso soa robótico. Termina com as hashtags."))
    # Thumbnail (estilo MrBeast)
    thumb_texto: str = Field(default="", description="Texto da thumbnail (MÁX 4 palavras, PT-BR)")
    thumb_emocao: str = Field(default="", description="Gatilho emocional (choque, curiosidade, medo...)")
    thumb_visual: str = Field(default="", description="Sujeito visual principal da thumbnail")
    thumb_expressao: str = Field(default="", description="Expressão facial recomendada")
    thumb_contraste: str = Field(default="", description="Recomendação de contraste/cor")
    # Análise
    retencao: str = Field(default="", description="Análise de retenção (por que assistem até o fim)")
    publico: str = Field(default="", description="Público esperado")
    riscos: str = Field(default="", description="Fatores de risco (ou 'nenhum')")
    recomendacao: str = Field(default="Publicar", description="'Publicar' ou 'Não Publicar'")
    # Sub-scores (0-10) — modelo de retenção MrBeast
    s_hook: int = Field(default=0, description="Hook strength 0-10")
    s_curiosidade: int = Field(default=0, description="Curiosity gap 0-10")
    s_surpresa: int = Field(default=0, description="Surprise factor 0-10")
    s_emocao: int = Field(default=0, description="Emotional impact 0-10")
    s_share: int = Field(default=0, description="Shareability 0-10")
    s_retencao: int = Field(default=0, description="Completion potential 0-10")
    # Dimensões adicionais (framework de 13 agentes) — mesma escala 0-10
    s_controversia: int = Field(default=0, description="Potencial de discussão saudável 0-10 (NUNCA premiar ataque pessoal/preconceito/desinformação)")
    s_novidade: int = Field(default=0, description="Ideia/ângulo original vs genérico e repetido 0-10")
    s_autoridade: int = Field(default=0, description="Quanto fortalece a autoridade técnica do criador 0-10")
    s_densidade: int = Field(default=0, description="Densidade de informação útil por segundo 0-10 (denso mas compreensível, não só falar rápido)")
    s_ritmo: int = Field(default=0, description="Ritmo narrativo — variação, pausas, progressão de intensidade 0-10")
    s_tema: int = Field(default=0, description="Relevância do tema pro público-alvo, tamanho de audiência potencial 0-10")
    # Justificativas — obrigatório, não pode dar nota sem explicar
    controversia_afirmacao: str = Field(default="", description="A afirmação controversa específica do trecho, se houver (ou 'nenhuma')")
    novidade_elemento: str = Field(default="", description="O que especificamente é novo/original nesse trecho (ou 'nenhum, é genérico')")
    elegivel: bool = Field(default=True, description="False se o trecho deveria ser ELIMINADO: s_hook<4.5 OU s_retencao<5.0 OU depende de contexto anterior OU corta frase no meio OU não entrega o que promete")
    motivo_eliminacao: str = Field(default="", description="Se elegivel=False, explica exatamente qual regra de eliminação foi violada")
    # Ajuste por histórico REAL do canal (seção 11 do framework) — só
    # aplicado quando existe dado de verdade suficiente (ver Growth)
    tipo_gancho: str = Field(default="nenhum_claro", description=f"Classifique o hook desse clip num desses tipos: {', '.join(_TIPOS_GANCHO)}")
    historico_ajuste: int = Field(default=0, description="Ajuste de -10 a +10 no score final, baseado em como esse tipo de gancho performou DE VERDADE no histórico real do canal (0 se não há dado histórico suficiente ainda)")
    historico_motivo: str = Field(default="", description="Por que esse ajuste — cita o dado real (ex: 'gancho de choque teve 3x mais views no seu perfil') ou 'sem dado histórico suficiente'")


class HighlightsOutput(BaseModel):
    highlights: list[Highlight]


# Pesos da fórmula de score (somam 1.0) — mesma lógica do framework de 13
# agentes, mas calculada aqui em código, não pela IA "somando sozinha".
# Isso é mais rigoroso e auditável: dá pra conferir exatamente de onde
# veio cada ponto do viral_score final, e a IA não pode inflar a nota
# geral sem justificar cada sub-score individualmente.
_PESOS_SCORE = {
    "s_hook": 0.18, "s_retencao": 0.18, "s_curiosidade": 0.12,
    "s_emocao": 0.08, "s_tema": 0.10, "s_share": 0.08,
    "s_controversia": 0.05, "s_novidade": 0.06, "s_autoridade": 0.05,
    "s_densidade": 0.05, "s_ritmo": 0.05,
}


def calcular_viral_score(h: "Highlight") -> int:
    """Calcula o viral_score (0-100) a partir dos sub-scores (0-10),
    pela fórmula de pesos — nunca confia no que a IA colocou direto no
    campo viral_score. Depois aplica o ajuste por histórico real do
    canal (-10 a +10, seção 11 do framework) — só quando a IA indicou
    ter dado real suficiente pra isso (historico_ajuste != 0)."""
    soma_ponderada = sum(
        getattr(h, campo, 0) * peso for campo, peso in _PESOS_SCORE.items()
    )
    base = soma_ponderada * 10
    ajuste = max(-10, min(10, getattr(h, "historico_ajuste", 0) or 0))
    return max(0, min(100, round(base + ajuste)))


def deve_eliminar(h: "Highlight") -> bool:
    """Regra de eliminação (seção 6 do framework): hook fraco ou retenção
    fraca elimina o clip, MESMO que a IA tenha marcado elegivel=True —
    dupla checagem em código, não confia só no julgamento da IA."""
    return (h.s_hook < 4.5) or (h.s_retencao < 5.0) or (not h.elegivel)


class HighlightExtractorInput(BaseModel):
    segments_path: str = Field(
        description="Caminho para o JSON de segmentos com timestamps"
    )
    niche: str = Field(description="Nicho/tema do vídeo")
    content_type: str = Field(
        default="shorts",
        description="Tipo: shorts | cortes_medio | cortes_longo",
    )


class HighlightExtractorTool(BaseTool):
    name: str = "highlight_extractor"
    description: str = (
        "Identifica os momentos mais virais e impactantes de um vídeo. "
        "Suporta Shorts (30-45s), cortes médios (2-5 min) e longos "
        "(5-15 min). Retorna JSON com highlights, tipo, viral score, "
        "hook de abertura e hashtags. Use após a transcrição."
    )
    args_schema: type[BaseModel] = HighlightExtractorInput
    llm_model: str = "gpt-4o-mini"

    @staticmethod
    def _build_historical_context() -> str:
        """Busca o resumo real de performance por tipo de gancho (Growth,
        analytics/store.py) e formata pra injetar no prompt. Fail-open
        total: se o banco não estiver acessível, ou não houver dado
        suficiente ainda, devolve uma frase explícita dizendo isso — a
        IA é instruída a não aplicar nenhum ajuste nesse caso, em vez de
        inventar um padrão que não existe."""
        try:
            from analytics.store import resumo_por_gancho
            resumo = resumo_por_gancho(plataforma="instagram")
        except Exception as e:
            print(f"[highlight_extractor] Sem acesso ao histórico do Growth: {e}")
            return "Nenhum dado histórico disponível ainda (banco de analytics inacessível)."

        total_analisado = sum(r.get("n", 0) for r in resumo)
        if total_analisado < 5:
            return (
                f"Dado histórico ainda insuficiente ({total_analisado} post(s) "
                "analisado(s) no Growth — precisa de mais pra confiar num padrão)."
            )

        linhas = ["Performance REAL por tipo de gancho no perfil do usuário (Growth):"]
        for r in resumo:
            linhas.append(
                f"- {r['tipo_gancho']}: {r['n']} post(s), média de "
                f"{r['media_views']:.0f} views reais"
            )
        return "\n".join(linhas)

    def _run(
        self,
        segments_path: str,
        niche: str,
        content_type: str = "shorts",
        num_highlights: int | None = None,
    ) -> str:
        if not Path(segments_path).exists():
            return f"ERRO: segmentos não encontrados: {segments_path}"

        with open(segments_path, encoding="utf-8") as f:
            segments = json.load(f)

        if not segments:
            return "ERRO: arquivo de segmentos vazio."

        historico_contexto = self._build_historical_context()

        cfg = _CONTENT_CONFIGS.get(content_type, _CONTENT_CONFIGS["shorts"])

        # Quantidade: N exato se pedido, senão a faixa do tipo (fonte: clip_rules)
        qty_min, qty_max = resolve_qty(content_type, num_highlights)

        total = segments[-1]["end"]
        # cobre o vídeo INTEIRO dentro do orçamento (corrige cortes só do começo)
        transcript, amostrado = build_transcript_view(segments, budget_chars=14000)
        cobertura = ("\nATENÇÃO: a transcrição abaixo foi AMOSTRADA ao longo de TODO "
                     "o vídeo (ela é longa). Distribua os cortes do início ao fim, "
                     "não concentre só no começo.\n") if amostrado else ""

        from tools.llm_fallback import build_llm_with_fallback
        llm = build_llm_with_fallback(
            temperature=0.3, primary_provider="openai", primary_model=self.llm_model,
        )
        parser = PydanticOutputParser(pydantic_object=HighlightsOutput)

        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "Você é um ESTRATEGISTA DE CONTEÚDO VIRAL DE ELITE, inspirado nos "
                "princípios usados pelo MrBeast. Sua missão NÃO é achar momentos "
                "interessantes — é achar momentos que MAXIMIZEM: CTR, retenção, "
                "curiosity gap, resposta emocional, compartilhamento e replay.\n\n"
                "Analise toda a transcrição e selecione EXATAMENTE {qty_max} "
                "momentos com FORTE potencial viral para criar {label} "
                "(se o vídeo não tiver material para tantos, traga o máximo possível "
                "de momentos realmente bons). "
                "Cada clip deve ter entre {min_seg} e {max_seg} segundos. {focus}\n\n"
                "OBRIGATÓRIO: preencha SEMPRE o campo 'titulo' com o melhor título "
                "viral (nunca deixe vazio) e 'titulos_alt' com 10 alternativos.\n\n"
                "PRIORIZE momentos com: fatos inesperados, mistérios históricos, "
                "revelações surpreendentes, verdades contraintuitivas, segredos, "
                "mitos sendo destruídos, momentos 'ninguém sabe', descobertas, "
                "comparações fascinantes, tecnologias antigas, civilizações perdidas, "
                "comportamento humano extremo, guerra, mistérios religiosos, "
                "arqueologia, eventos estranhos, história oculta, conhecimento raro.\n"
                "EVITE: introduções longas, saudações, conversa fiada, explicações "
                "genéricas, trechos de baixo impacto emocional, repetição.\n\n"
                "Para CADA momento candidato, avalie (0-10) e preencha os sub-scores: "
                "hook strength (s_hook), curiosity gap (s_curiosidade), surprise "
                "(s_surpresa), emotional impact (s_emocao), shareability (s_share), "
                "completion potential (s_retencao), potencial de discussão saudável "
                "sem ataque pessoal/desinformação (s_controversia), originalidade do "
                "ângulo vs. genérico e repetido (s_novidade), quanto fortalece a "
                "autoridade técnica do criador (s_autoridade), densidade de "
                "informação útil por segundo — denso mas compreensível "
                "(s_densidade), ritmo narrativo — variação, pausas, progressão "
                "(s_ritmo), relevância do tema pro público-alvo (s_tema). NÃO some "
                "os sub-scores nem calcule um total — o viral_score final é "
                "calculado à parte, por fórmula, a partir dos seus sub-scores. Seja "
                "criterioso: notas altas em tudo pra todo clip não ajuda ninguém, "
                "use a escala inteira.\n\n"
                "elegivel=False quando: s_hook<4.5 OU s_retencao<5.0 OU o trecho "
                "depende demais de contexto anterior OU corta uma frase no meio OU "
                "não entrega o que promete no início. Quando elegivel=False, "
                "preencha motivo_eliminacao explicando qual regra foi violada — "
                "esses clips ainda aparecem na resposta, mas serão descartados "
                "depois.\n\n"
                "CLASSIFIQUE em tier: S = potencial 1M+ | A = 500k+ | B = 100k+ | "
                "C = médio. Selecione APENAS clips tier S e A.\n\n"
                "HISTÓRICO REAL DO CANAL (Growth):\n{historico}\n"
                "Classifique o hook de cada clip em tipo_gancho (mesma taxonomia "
                "do histórico acima). Se o histórico tiver dado suficiente "
                "(não disser 'insuficiente' nem 'inacessível'), compare o "
                "tipo_gancho desse clip com o que já performou de verdade nesse "
                "canal específico — preencha historico_ajuste (-10 a +10) e "
                "historico_motivo citando o número real. O histórico do canal "
                "vale MAIS que regra genérica de mercado. Se o histórico for "
                "insuficiente/inacessível, deixe historico_ajuste=0 e diga isso "
                "em historico_motivo — nunca invente um padrão que não existe.\n\n"
                "Para cada clip gere também: o melhor título + 10 títulos virais "
                "alternativos (titulos_alt), um hook OTIMIZADO mais forte que o "
                "original (hook_otimizado), uma DESCRIÇÃO viral otimizada para SEO "
                "(descricao: gancho na 1ª linha + valor + chamada para ação + "
                "hashtags), análise de retenção (retencao), público (publico), "
                "riscos (riscos) e a recomendação final (recomendacao: 'Publicar' ou "
                "'Não Publicar').\n\n"
                "CONCEITO DE THUMBNAIL — pense como estrategista de thumbnail, não "
                "designer. O objetivo é criar uma DECISÃO DE CLIQUE em menos de 1 "
                "segundo, do tamanho de um selo postal, na tela de um celular:\n"
                "- thumb_texto: MÁXIMO 4 palavras. Se precisar de mais, o conceito "
                "não está claro o suficiente.\n"
                "- A thumbnail COMPLEMENTA o título, nunca repete. Se o título já diz "
                "o fato, a thumbnail mostra a REAÇÃO/CONSEQUÊNCIA/PROVA visual dele — "
                "nunca as mesmas palavras.\n"
                "- thumb_emocao: uma emoção específica e genuína (choque, ceticismo, "
                "medo, êxtase) — nunca 'sorrindo' ou algo genérico, isso não é "
                "emoção.\n"
                "- thumb_expressao: descreva a expressão facial exata que comunica "
                "essa emoção sozinha, sem depender do texto.\n"
                "- thumb_contraste: cor/contraste que sobrevive ao lado de 20+ outras "
                "thumbnails concorrendo na mesma tela — nunca sugira paleta "
                "apagada/pastel.\n"
                "- Máximo 3 elementos visuais no total (ex: rosto + texto, ou rosto + "
                "objeto) — mais que isso vira ruído visual e ninguém entende em 1 "
                "segundo.\n\n"
                "Não use clickbait sem lastro no conteúdo. "
                "Se o vídeo for entrevista/podcast com pessoa conhecida, destaque o "
                "NOME e as falas mais polêmicas ou surpreendentes dela.\n\n"
                f"{ANTI_SLOP_RULES}\n"
                "Responda em PORTUGUÊS BRASILEIRO.\n\n{format_instructions}"
            )),
            ("human", (
                "Nicho: {niche}\n"
                "Formato: {label}\n"
                "Duração total do vídeo: {total:.0f}s\n"
                "Quero EXATAMENTE {qty_max} clips — não retorne menos que isso se a "
                "transcrição permitir. Distribua-os ao longo de todo o vídeo.{cobertura}\n"
                "Para CADA clip, o campo 'titulo' é OBRIGATÓRIO e deve ser o melhor "
                "título viral (não deixe vazio).\n"
                "Caça especialmente: PONTOS DE POLÊMICA, picos de EMOÇÃO, uma "
                "LIÇÃO interessante, CURIOSIDADES e revelações que quebram o senso "
                "comum. Cada clip deve ter um desses ganchos.\n\n"
                "Transcrição ([segundos] texto):\n{transcript}\n\n"
                "Selecione os melhores clips para {label}, distribuídos pelo vídeo."
            )),
        ])

        chain = prompt | llm | parser

        try:
            print(
                f"[highlight_extractor] Analisando highlights "
                f"({cfg['label']})..."
            )
            result: HighlightsOutput = chain.invoke({
                "niche":             niche,
                "label":             cfg["label"],
                "min_seg":           cfg["min_seg"],
                "max_seg":           cfg["max_seg"],
                "qty_min":           qty_min,
                "qty_max":           qty_max,
                "focus":             cfg["focus"],
                "cobertura":         cobertura,
                "transcript":        transcript,
                "total":             total,
                "historico":         historico_contexto,
                "format_instructions": parser.get_format_instructions(),
            })
            n = len(result.highlights)
            print(f"[highlight_extractor] {n} highlights identificados.")
        except Exception as e:
            # Rede de segurança: tenta recuperar o JSON cru e preencher defaults,
            # para não jogar fora 5 ótimos cortes por um campo faltando.
            recovered = self._recover_highlights(llm, prompt, parser, {
                "niche": niche, "label": cfg["label"], "min_seg": cfg["min_seg"],
                "max_seg": cfg["max_seg"], "qty_min": qty_min, "qty_max": qty_max,
                "focus": cfg["focus"], "cobertura": cobertura,
                "transcript": transcript, "total": total,
                "historico": historico_contexto,
                "format_instructions": parser.get_format_instructions(),
            })
            if recovered is not None:
                result = recovered
                print(f"[highlight_extractor] recuperados {len(result.highlights)} "
                      "highlights via fallback.")
            else:
                return f"ERRO ao extrair highlights: {e}"

        # Seleção: se o usuário pediu uma quantidade, RESPEITA (top N por score).
        # Sem quantidade pedida, mantém só tier S/A (modo "melhores automáticos").
        hls = result.highlights
        # corrige título vazio usando o melhor título alternativo (a IA às vezes
        # preenche titulos_alt mas esquece o titulo principal)
        for h in hls:
            if (not h.titulo) or h.titulo.strip().lower() in ("", "clip sem título",
                                                              "clip sem titulo"):
                if h.titulos_alt:
                    h.titulo = h.titulos_alt[0]
                elif h.hook_otimizado:
                    h.titulo = h.hook_otimizado

        # Elimina os que violam a regra de corte (seção 6 do framework) —
        # dupla checagem em código, não confia só no julgamento da IA.
        # Loga o motivo pra debug, mas não trava o pipeline por isso.
        eliminados = [h for h in hls if deve_eliminar(h)]
        hls = [h for h in hls if not deve_eliminar(h)]
        for h in eliminados:
            motivo = h.motivo_eliminacao or f"s_hook={h.s_hook} s_retencao={h.s_retencao}"
            print(f"[highlight_extractor] Eliminado ({h.titulo[:40]!r}): {motivo}")

        # Recalcula o viral_score de cada clip que sobrou POR FÓRMULA —
        # nunca confia no número que a IA colocou direto no campo
        # viral_score, mesmo que ela tenha tentado somar sozinha.
        for h in hls:
            h.viral_score = calcular_viral_score(h)

        hls.sort(key=lambda h: h.viral_score or 0, reverse=True)
        if num_highlights and num_highlights > 0:
            chosen = hls[:num_highlights]
            if len(chosen) < num_highlights:
                print(f"[highlight_extractor] IA retornou {len(chosen)} de "
                      f"{num_highlights} pedidos; rodando passe de reforço...")
                extra = self._fill_pass(llm, parser, niche, cfg, transcript,
                                        total, cobertura, chosen,
                                        num_highlights - len(chosen))
                chosen = self._merge_dedup(chosen + extra, num_highlights)
        else:
            sa = [h for h in hls if (h.tier or "").upper().strip() in ("S", "A")]
            chosen = sa if sa else hls[:max(1, qty_min)]
        result.highlights = chosen
        # Normaliza o título: se o principal veio vazio/placeholder, usa o melhor
        # título alternativo (ou o hook otimizado). Evita "Clip sem título".
        for h in result.highlights:
            t = (h.titulo or "").strip()
            if not t or t.lower() == "clip sem título":
                if h.titulos_alt:
                    h.titulo = h.titulos_alt[0]
                elif h.hook_otimizado:
                    h.titulo = h.hook_otimizado
                elif h.thumb_texto:
                    h.titulo = h.thumb_texto
        print(f"[highlight_extractor] {len(chosen)} clips selecionados "
              f"(pedido: {num_highlights or 'auto'}).")

        return json.dumps(result.model_dump(), ensure_ascii=False)

    async def _arun(self, **kwargs) -> str:
        return self._run(**kwargs)

    def _second_llm(self):
        """Modelo do passe de reforço — usa Claude se configurado
        (orquestração), com fallback real pro GPT se o Claude falhar em
        tempo de execução (não só se estiver ausente na configuração)."""
        from tools.llm_fallback import build_llm_with_fallback
        model = os.getenv("CLIP_FILL_MODEL", "")
        if model.startswith("claude"):
            return build_llm_with_fallback(
                temperature=0.5, primary_provider="anthropic", primary_model=model,
                fallback_provider="openai", fallback_model=self.llm_model,
            )
        return build_llm_with_fallback(
            temperature=0.6, primary_provider="openai", primary_model=self.llm_model,
        )

    def _fill_pass(self, llm, parser, niche, cfg, transcript, total, cobertura,
                   ja_escolhidos, faltam):
        """Segundo passe: pede MAIS cortes, evitando os trechos já usados."""
        usados = "; ".join(f"{h.inicio:.0f}-{h.fim:.0f}s" for h in ja_escolhidos)
        fill_llm = self._second_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "Você é um estrategista viral. Encontre MAIS {faltam} cortes de alto "
                "potencial viral ({min_seg}-{max_seg}s) na transcrição, em trechos "
                "DIFERENTES dos já usados. {focus} Caça polêmica, emoção, lição e "
                "curiosidade. Responda em PT-BR.\n\nJÁ USADOS (evite estes intervalos): "
                "{usados}\n\n{format_instructions}"
            )),
            ("human", "Nicho: {niche}\nDuração: {total:.0f}s\n{cobertura}\n"
                      "Transcrição:\n{transcript}"),
        ])
        try:
            res = (prompt | fill_llm | parser).invoke({
                "faltam": faltam, "min_seg": cfg["min_seg"], "max_seg": cfg["max_seg"],
                "focus": cfg["focus"], "usados": usados, "niche": niche,
                "total": total, "cobertura": cobertura, "transcript": transcript,
                "format_instructions": parser.get_format_instructions(),
            })
            for h in res.highlights:
                if (not h.titulo or "sem títul" in h.titulo.lower()) and h.titulos_alt:
                    h.titulo = h.titulos_alt[0]
            # mesma correção do fluxo principal: elimina quem viola a regra
            # de corte, recalcula o score por fórmula — sem isso, os clips
            # do passe de reforço escapariam da mesma régua dos primeiros.
            extras = [h for h in res.highlights if not deve_eliminar(h)]
            for h in extras:
                h.viral_score = calcular_viral_score(h)
            return extras
        except Exception as e:
            print(f"[highlight_extractor] passe de reforço falhou: {e}")
            return []

    @staticmethod
    def _merge_dedup(highlights, limit):
        """Une listas removendo cortes que se sobrepõem no tempo; mantém top por score."""
        highlights.sort(key=lambda h: h.viral_score or 0, reverse=True)
        kept = []
        for h in highlights:
            overlap = any(not (h.fim <= k.inicio or h.inicio >= k.fim) for k in kept)
            if not overlap:
                kept.append(h)
            if len(kept) >= limit:
                break
        return kept

    def _recover_highlights(self, llm, prompt, parser, vars_):
        """
        Fallback: chama o modelo só pelo texto, extrai o JSON cru e cria os
        Highlight preenchendo defaults para campos faltantes (ex.: hashtags).
        Assim a resposta não é descartada por um único campo ausente.
        """
        import re as _re
        try:
            raw = (prompt | llm).invoke(vars_)
            text = getattr(raw, "content", raw)
            if isinstance(text, list):
                text = " ".join(str(t) for t in text)
            # extrai o maior bloco { ... } da resposta
            m = _re.search(r"\{.*\}", text, _re.DOTALL)
            if not m:
                return None
            data = json.loads(m.group(0))
            items = data.get("highlights", data if isinstance(data, list) else [])
            highlights = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                # inicio/fim são obrigatórios de verdade; sem eles, descarta o item
                if "inicio" not in it or "fim" not in it:
                    continue
                try:
                    highlights.append(Highlight(**it))   # defaults cobrem o resto
                except Exception:
                    continue
            if not highlights:
                return None
            return HighlightsOutput(highlights=highlights)
        except Exception as err:
            print(f"[highlight_extractor] fallback falhou: {err}")
            return None
