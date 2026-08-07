"""
tools/caption_translator.py — traduz o TEXTO das legendas (mantendo os
timestamps intactos) via Claude. Usado quando o vídeo fonte está num
idioma e você quer a legenda queimada em outro (ex: vídeo em inglês,
legenda em português).

Por que traduzir em vez de só transcrever no idioma alvo: o Whisper
transcreve no idioma FALADO (ou traduz só pra inglês, uma limitação
conhecida dele — não serve pra traduzir pra português). Pra qualquer
outro idioma de destino, precisa de um passo de tradução de verdade —
é isso que esse módulo faz, com um LLM de texto (Claude).

Credenciais (.env): ANTHROPIC_API_KEY (mesma chave já usada em
tools/claude_copy_client.py e em todo o resto do projeto).
"""

from __future__ import annotations

import json
import os

from tools.llm_fallback import LLMFallbackError

import anthropic

MODEL = os.getenv("CLAUDE_COPY_MODEL", "claude-haiku-4-5-20251001")

LANG_LABELS = {
    "pt": "português do Brasil",
    "en": "inglês",
    "es": "espanhol",
}


class CaptionTranslationError(RuntimeError):
    """Erro ao traduzir a legenda."""


def is_alive() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def translate_segments(segments: list[dict], idioma_alvo: str, batch_size: int = 60) -> list[dict]:
    """Traduz o campo 'text' de uma lista de SEGMENTOS DA TRANSCRIÇÃO
    INTEIRA (mantendo start/end intactos), em lotes — pra não estourar o
    limite de contexto/saída numa transcrição longa (vídeo de 20min pode
    ter centenas de segmentos).

    Por que traduzir a transcrição inteira UMA VEZ, em vez de traduzir a
    legenda de cada clip separadamente: cada chamada de API é um ponto de
    falha independente (rate limit, erro pontual, contagem que não bate).
    Traduzindo clip a clip, um vídeo com 15 clips vira 15 chances de
    falhar — e cada falha cai no fail-open (legenda original), dando o
    resultado inconsistente "alguns em português, outros não". Traduzindo
    a transcrição inteira uma vez só, ou dá tudo certo (todo clip sai
    traduzido) ou falha uma vez só (todo clip cai no idioma original,
    mas de forma CONSISTENTE, não misturada).

    Retorna uma NOVA lista de segmentos (não muta a original) — cada um
    com o mesmo start/end, texto traduzido, sem o campo 'words' (a
    tradução é por segmento, não por palavra individual)."""
    if not segments:
        return []

    textos = [s.get("text", "") for s in segments]
    traduzidos: list[str] = []
    for i in range(0, len(textos), batch_size):
        lote = textos[i:i + batch_size]
        traduzidos.extend(translate_caption_texts(lote, idioma_alvo))

    if len(traduzidos) != len(segments):
        raise CaptionTranslationError(
            f"Tradução da transcrição veio com {len(traduzidos)} segmento(s), "
            f"esperava {len(segments)} — abortando pra não bagunçar o timing."
        )

    novos = []
    for seg, texto_traduzido in zip(segments, traduzidos):
        novo = dict(seg)
        novo["text"] = texto_traduzido
        novo.pop("words", None)  # tradução é por segmento, não por palavra
        novos.append(novo)
    return novos


def _call_translate_indexed(itens: list[dict], idioma_label: str) -> dict[int, str]:
    """Uma chamada à API. Manda itens {i, t} (índice + texto), pede de
    volta no mesmo formato. Usar índice explícito (em vez de só confiar
    na ordem da lista) permite saber EXATAMENTE quais blocos vieram
    certos, mesmo que a IA erre a contagem — em vez de "tudo ou nada"."""
    system = (
        f"Você traduz legendas de vídeo pro {idioma_label}. Recebe uma lista "
        "JSON de objetos {\"i\": índice, \"t\": texto} — cada um é UM bloco "
        "de legenda (podem ser frases cortadas no meio, é normal, legenda "
        "funciona assim). Devolva a tradução de CADA item, no MESMO formato "
        "{\"i\": índice, \"t\": tradução} — o índice \"i\" tem que ser "
        "IDÊNTICO ao que veio, é assim que a tradução volta pro lugar certo "
        "no vídeo. Nunca junte dois itens num só, nunca pule nenhum, mesmo "
        "que o corte pareça estranho isolado. Tradução natural e coloquial "
        "(é legenda de vídeo curto, não texto formal), curta o suficiente "
        "pra caber na tela. Responda APENAS com a lista JSON de objetos "
        "{\"i\": ..., \"t\": ...}. Nada de texto antes ou depois."
    )
    user = json.dumps(itens, ensure_ascii=False)

    # call_with_fallback: se a Anthropic falhar de verdade (fora do ar,
    # rate limit, erro de API — não erro de conteúdo), cai pra OpenAI
    # sozinho, sem quebrar a tradução por causa de UM provedor indisponível.
    from tools.llm_fallback import call_with_fallback
    raw = call_with_fallback(system, user, max_tokens=4096, anthropic_model=MODEL).strip()
    if not raw:
        raise CaptionTranslationError("Resposta da API veio vazia")
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
    parsed = json.loads(raw)

    resultado: dict[int, str] = {}
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict) and "i" in item and "t" in item:
                try:
                    resultado[int(item["i"])] = str(item["t"])
                except (ValueError, TypeError):
                    continue
    return resultado


def translate_caption_texts(textos: list[str], idioma_alvo: str) -> list[str]:
    """Traduz uma lista de textos de legenda pro idioma_alvo ('pt'/'en'/'es'),
    preservando a ORDEM e a QUANTIDADE exatas na saída — 1 texto de
    entrada = 1 texto de saída, sempre, pra o timing de cada bloco nunca
    ficar bagunçado.

    Tenta até 2 vezes por bloco que não veio certo (a IA às vezes erra a
    contagem ou funde dois blocos). O que ainda assim não vier em
    NENHUMA tentativa fica no texto ORIGINAL — fallback parcial, é
    melhor 1 legenda no idioma errado no meio do vídeo do que perder a
    tradução inteira por causa de 1 bloco perdido.
    """
    if not textos:
        return []
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise CaptionTranslationError("ANTHROPIC_API_KEY não configurada no .env")

    idioma_label = LANG_LABELS.get(idioma_alvo, idioma_alvo)
    itens = [{"i": i, "t": t} for i, t in enumerate(textos)]

    encontrados: dict[int, str] = {}
    ultimo_erro: Exception | None = None
    for tentativa in range(2):
        faltando = [item for item in itens if item["i"] not in encontrados]
        if not faltando:
            break
        try:
            encontrados.update(_call_translate_indexed(faltando, idioma_label))
        except (anthropic.APIError, json.JSONDecodeError, LLMFallbackError) as e:
            ultimo_erro = e
            continue  # tenta de novo (só resta 1 tentativa no máximo)

    if not encontrados and ultimo_erro is not None:
        # as 2 tentativas falharam de vez (erro de API/parsing, não só
        # contagem) — nesse caso sim, propaga o erro pra quem chamou
        # decidir (build_srt cai pro texto original inteiro).
        raise CaptionTranslationError(f"Falha ao traduzir legendas: {ultimo_erro}")

    faltantes = [i for i in range(len(textos)) if i not in encontrados]
    if faltantes:
        print(f"[caption_translator] {len(faltantes)}/{len(textos)} bloco(s) "
              f"ficaram no idioma original (a IA não devolveu esses índices "
              f"mesmo após retry) — resto traduzido normalmente.")

    return [encontrados.get(i, textos[i]) for i in range(len(textos))]
