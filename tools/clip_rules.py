"""
tools/clip_rules.py — regras puras de corte (sem dependências externas).

Centraliza a configuração por tipo de conteúdo e a lógica de consistência:
quantidade de cortes, limites de duração e densidade de fala. Sem langchain,
sem rede — fácil de testar e reaproveitado pelo extrator e pelo pipeline.
"""

from __future__ import annotations

MAX_CLIPS = 15   # teto absoluto de cortes por vídeo

_SHORTS_FOCUS = (
    "Priorize: hooks que prendem nos primeiros 3 segundos, revelações "
    "surpresa, emoções intensas e opiniões polêmicas. O clip deve ser "
    "autocontido — o espectador entende sem contexto prévio."
)
_CORTE_FOCUS = (
    "Priorize: explicações completas, demonstrações, entrevistas e debates "
    "substanciais. O clip deve ter início, meio e fim claros e ser uma "
    "unidade de conhecimento independente."
)

# Tipos de gancho da biblioteca de growth — fonte única, usada tanto na
# análise de padrão de posts reais (analytics/growth_analyzer.py) quanto
# na seleção de clips (highlight_extractor.py) — pra comparar "gancho
# que o clip usa" com "gancho que já funcionou de verdade" apples-to-apples.
TIPOS_GANCHO = [
    "choque", "parar_acao", "economia", "pergunta",
    "antes_depois", "erro_aviso", "pov", "numeros_lista", "nenhum_claro",
]

CONTENT_CONFIGS = {
    # ── Presets de duração específicos (novos) ──
    "shorts_30": {"label": "Short 30s", "min_seg": 22, "max_seg": 38,
                  "qty_min": 4, "qty_max": 12, "focus": _SHORTS_FOCUS},
    "shorts_45": {"label": "Short 45s", "min_seg": 36, "max_seg": 55,
                  "qty_min": 4, "qty_max": 12, "focus": _SHORTS_FOCUS},
    "shorts_90": {"label": "Short 1:30", "min_seg": 75, "max_seg": 105,
                  "qty_min": 3, "qty_max": 10, "focus": _SHORTS_FOCUS},
    "corte_120": {"label": "Corte 2 min", "min_seg": 95, "max_seg": 150,
                  "qty_min": 3, "qty_max": 10, "focus": _CORTE_FOCUS},
    "corte_300": {"label": "Corte 5 min", "min_seg": 250, "max_seg": 360,
                  "qty_min": 2, "qty_max": 8, "focus": _CORTE_FOCUS},
    "corte_600": {"label": "Corte 10 min", "min_seg": 520, "max_seg": 700,
                  "qty_min": 2, "qty_max": 6, "focus": _CORTE_FOCUS},
    "corte_900": {"label": "Corte 15 min", "min_seg": 780, "max_seg": 1020,
                  "qty_min": 1, "qty_max": 4, "focus": _CORTE_FOCUS},
    # ── Compat com os tipos antigos ──
    "shorts": {"label": "YouTube Shorts / Reels / TikTok",
               "min_seg": 36, "max_seg": 55, "qty_min": 4, "qty_max": 12,
               "focus": _SHORTS_FOCUS},
    "cortes_medio": {"label": "Cortes médios (2–5 min)",
                     "min_seg": 120, "max_seg": 300, "qty_min": 3,
                     "qty_max": 8, "focus": _CORTE_FOCUS},
    "cortes_longo": {"label": "Cortes longos (5–15 min)",
                     "min_seg": 300, "max_seg": 900, "qty_min": 2,
                     "qty_max": 4, "focus": _CORTE_FOCUS},
}


def get_config(content_type: str) -> dict:
    return CONTENT_CONFIGS.get(content_type, CONTENT_CONFIGS["shorts"])


def clip_bounds(content_type: str) -> tuple[int, int]:
    cfg = get_config(content_type)
    return cfg["min_seg"], cfg["max_seg"]


def resolve_qty(content_type: str, num_highlights: int | None) -> tuple[int, int]:
    """Se o usuário pediu N exato, fixa (N, N) limitado a MAX_CLIPS; senão a faixa."""
    if num_highlights and num_highlights > 0:
        n = min(int(num_highlights), MAX_CLIPS)
        return n, n
    cfg = get_config(content_type)
    return cfg["qty_min"], cfg["qty_max"]


def max_clips_for_duration(duration_s: float, min_seg: int) -> int:
    """Quantos cortes de pelo menos `min_seg` cabem em `duration_s`."""
    if duration_s <= 0 or min_seg <= 0:
        return 1
    return max(1, int(duration_s // min_seg))


def speech_wpm(word_count: int, duration_s: float) -> float:
    """Palavras por minuto. 0 se a duração for desconhecida."""
    if duration_s <= 0:
        return 0.0
    return word_count / (duration_s / 60.0)


def is_low_speech(wpm: float, threshold: float) -> bool:
    """True se o vídeo tem pouca fala (música/instrumental)."""
    return 0 < wpm < threshold


def enforce_durations(
    highlights: list[dict],
    min_seg: int,
    max_seg: int,
    total_duration: float = 0.0,
) -> tuple[list[dict], int, int]:
    """
    Garante que CADA corte respeite [min_seg, max_seg] — o LLM só recebe isso
    como sugestão, então aqui é onde a regra vira lei.

    - curto demais  → estende o fim (recuando o início se faltar espaço);
    - longo demais  → apara o fim;
    - inválido (início fora do vídeo / sem duração possível) → descarta.

    Retorna (lista_corrigida, n_ajustados, n_descartados).
    """
    cleaned, adjusted, dropped = [], 0, 0
    for h in highlights:
        try:
            inicio = max(0.0, float(h.get("inicio", 0)))
            fim = float(h.get("fim", 0))
        except (TypeError, ValueError):
            dropped += 1
            continue

        if total_duration > 0 and inicio >= total_duration:
            dropped += 1
            continue

        dur = fim - inicio
        changed = False

        if dur < min_seg:                      # curto demais → estende
            fim = inicio + min_seg
            changed = True
        elif dur > max_seg:                    # longo demais → apara
            fim = inicio + max_seg
            changed = True

        if total_duration > 0 and fim > total_duration:
            fim = total_duration
            # se ficou curto demais ao bater no fim do vídeo, recua o início
            if fim - inicio < min_seg:
                inicio = max(0.0, fim - min_seg)
            changed = True

        if fim - inicio < 1:                   # sem corte possível
            dropped += 1
            continue

        if changed:
            adjusted += 1
        item = dict(h)
        item["inicio"], item["fim"] = round(inicio, 2), round(fim, 2)
        cleaned.append(item)

    return cleaned, adjusted, dropped


def build_transcript_view(segments: list[dict], budget_chars: int = 14000):
    """
    Monta a transcrição para o LLM cobrindo o VÍDEO INTEIRO dentro de um orçamento.

    Em vídeos longos (podcasts), cortar os primeiros N chars faz o modelo só ver
    o começo e não achar cortes no resto. Aqui, se não couber tudo, amostramos
    trechos uniformemente ao longo de toda a duração, preservando os timestamps.

    Retorna (texto, amostrado: bool).
    """
    if not segments:
        return "", False
    lines = [f"[{s.get('start', 0):.0f}s] {s.get('text', '')}" for s in segments]
    full = "\n".join(lines)
    if len(full) <= budget_chars:
        return full, False

    avg = max(1, len(full) // max(1, len(lines)))
    keep = max(10, budget_chars // avg)
    if keep >= len(lines):
        return full[:budget_chars], True

    step = len(lines) / keep
    idxs = sorted({int(i * step) for i in range(keep)})
    # garante que o último segmento (fim do vídeo) entre na amostra
    if idxs[-1] != len(lines) - 1:
        idxs.append(len(lines) - 1)
    sampled = "\n".join(lines[i] for i in idxs)
    return sampled[:budget_chars + 200], True
