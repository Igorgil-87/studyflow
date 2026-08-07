"""
tools/captions.py — gera legenda (.srt) pra um clip específico, a partir da
transcrição COMPLETA do vídeo original (com timestamp por palavra).

Por que a partir da transcrição completa, não transcrever o clip de novo:
mais rápido (não roda o Whisper de novo) e mais preciso (usa o timestamp
já calculado, só recorta e realinha pro tempo relativo do clip).

Fluxo: full_segments (do vídeo inteiro) -> filtra as palavras dentro de
[clip_start, clip_end] -> desloca pra tempo relativo (0 = início do clip)
-> agrupa em blocos curtos de legenda (poucas palavras por vez, do jeito
que Shorts/Reels normalmente mostram) -> escreve .srt.
"""

from __future__ import annotations

MAX_WORDS_PER_CAPTION = 5   # poucas palavras por vez — legível em tela vertical
MAX_CHARS_PER_CAPTION = 34  # quebra antes disso mesmo com menos de 5 palavras
MAX_GAP_SECONDS = 0.6       # pausa de fala maior que isso -> força quebra de bloco
                            # (senão a legenda fica "grudada" atravessando um silêncio)


class CaptionsError(RuntimeError):
    """Erro ao gerar a legenda."""


def _collect_words(full_segments: list[dict], clip_start: float, clip_end: float) -> list[dict]:
    """Extrai todas as palavras (com timestamp já no tempo relativo do clip,
    0 = início do clip) que caem dentro de [clip_start, clip_end]."""
    words: list[dict] = []
    for seg in full_segments:
        seg_words = seg.get("words") or []
        if seg_words:
            for w in seg_words:
                w_start, w_end = w.get("start", 0), w.get("end", 0)
                # palavra precisa estar (ao menos parcialmente) dentro do clip
                if w_end <= clip_start or w_start >= clip_end:
                    continue
                words.append({
                    "word": (w.get("word") or "").strip(),
                    "start": max(0.0, w_start - clip_start),
                    "end": max(0.0, min(w_end, clip_end) - clip_start),
                })
        else:
            # fallback: segmento sem timing por palavra (transcrição antiga,
            # gerada antes do word_timestamps existir) -> distribui as
            # palavras linearmente dentro da duração do segmento
            s_start, s_end = seg.get("start", 0), seg.get("end", 0)
            if s_end <= clip_start or s_start >= clip_end:
                continue
            text_words = (seg.get("text") or "").split()
            if not text_words:
                continue
            dur = max(s_end - s_start, 0.01)
            step = dur / len(text_words)
            for i, tw in enumerate(text_words):
                w_start = s_start + i * step
                w_end = w_start + step
                if w_end <= clip_start or w_start >= clip_end:
                    continue
                words.append({
                    "word": tw,
                    "start": max(0.0, w_start - clip_start),
                    "end": max(0.0, min(w_end, clip_end) - clip_start),
                })
    words.sort(key=lambda w: w["start"])
    return words


def _group_into_captions(words: list[dict]) -> list[dict]:
    """Agrupa as palavras em blocos curtos de legenda (poucas palavras,
    limite de caracteres) — não uma frase inteira de uma vez."""
    captions: list[dict] = []
    buf: list[dict] = []

    def flush():
        if not buf:
            return
        text = " ".join(w["word"] for w in buf).strip()
        if text:
            captions.append({"start": buf[0]["start"], "end": buf[-1]["end"], "text": text})

    for w in words:
        candidate_text = " ".join([*(x["word"] for x in buf), w["word"]])
        gap_too_big = buf and (w["start"] - buf[-1]["end"] > MAX_GAP_SECONDS)
        if buf and (len(buf) >= MAX_WORDS_PER_CAPTION or len(candidate_text) > MAX_CHARS_PER_CAPTION or gap_too_big):
            flush()
            buf = []
        buf.append(w)
    flush()
    return captions


def _format_srt_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(full_segments: list[dict], clip_start: float, clip_end: float,
               translate_to: str | None = None) -> str:
    """Retorna o conteúdo de um arquivo .srt (string) pro trecho
    [clip_start, clip_end] do vídeo original, com timestamps já
    realinhados pro tempo relativo do clip (0 = início).

    translate_to: se informado ('pt'/'en'/'es'), traduz o TEXTO de cada
    bloco pro idioma alvo via Claude (ver tools/caption_translator.py) —
    o timing continua exatamente o mesmo, só o texto muda. Se a tradução
    falhar por qualquer motivo, cai de volta pro texto original (fail-open
    — melhor legenda no idioma errado do que nenhuma legenda)."""
    words = _collect_words(full_segments, clip_start, clip_end)
    if not words:
        raise CaptionsError("Nenhuma palavra com timestamp encontrada nesse intervalo.")
    captions = _group_into_captions(words)

    if translate_to:
        try:
            from tools.caption_translator import translate_caption_texts
            textos_traduzidos = translate_caption_texts(
                [c["text"] for c in captions], translate_to)
            for cap, novo_texto in zip(captions, textos_traduzidos):
                cap["text"] = novo_texto
        except Exception as e:
            print(f"[captions] Tradução falhou, usando texto original: {e}")

    lines = []
    for i, cap in enumerate(captions, start=1):
        lines.append(str(i))
        lines.append(f"{_format_srt_timestamp(cap['start'])} --> {_format_srt_timestamp(cap['end'])}")
        lines.append(cap["text"])
        lines.append("")
    return "\n".join(lines)


def write_srt_file(full_segments: list[dict], clip_start: float, clip_end: float,
                    out_path: str, translate_to: str | None = None) -> str:
    """Gera o .srt (opcionalmente traduzido) e salva em disco. Retorna o
    caminho salvo."""
    srt_content = build_srt(full_segments, clip_start, clip_end, translate_to=translate_to)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
    return out_path
