"""
tools/carousel_composer.py — aplica texto de VERDADE (renderizado por
fonte, não desenhado por um modelo de imagem) por cima de uma imagem de
fundo já gerada (Fooocus ou OpenAI).

Por que existir: nenhum gerador de imagem por IA (OpenAI, Fooocus, e
até os mais fortes do mercado) renderiza texto de forma 100% confiável —
sempre existe risco de letra deformada ou palavra errada. A solução:
gerar o FUNDO com IA (sem texto nenhum no prompt) e aplicar o texto por
cima com PIL — nítido, sempre correto, e ainda mais rápido/barato
(não precisa re-gerar a imagem se o texto mudar).

Uso:
    from tools import carousel_composer as cc
    cc.compose_slide(
        background_path="static/images/img_abc123_1.png",
        kicker="FINOPS", headline="A dor real não é migrar pra nuvem.",
        footer="É a fatura no fim do mês.",
        slide_number=1, slide_total=6,
        out_path="static/images/img_abc123_1_final.png",
    )
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

LIME = (198, 255, 61)
WHITE = (245, 245, 245)
GRAY = (210, 214, 224)

_FONT_DIR = "/usr/share/fonts/truetype/dejavu"
_FONT_BOLD = f"{_FONT_DIR}/DejaVuSans-Bold.ttf"
_FONT_REG = f"{_FONT_DIR}/DejaVuSans.ttf"


class ComposeError(RuntimeError):
    """Erro ao compor o slide final."""


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if draw.textlength(test, font=font) <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit_font_to_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    font_path: str,
    max_size: int,
    min_size: int,
    max_width: int,
    max_height: int,
    line_height_ratio: float = 1.15,
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    """Reduz o tamanho da fonte até o texto (com quebra de linha) caber
    inteiro na caixa disponível — GARANTE que o texto nunca fique cortado
    ou vaze pra fora do slide, custe o tamanho que custar."""
    size = max_size
    while size >= min_size:
        font = ImageFont.truetype(font_path, size)
        lines = _wrap(draw, text, font, max_width)
        line_h = int(size * line_height_ratio)
        total_h = len(lines) * line_h
        if total_h <= max_height:
            return font, lines, line_h
        size -= 2
    # nem no tamanho mínimo coube inteiro — usa o mínimo mesmo assim
    # (texto pode ficar apertado, mas nunca é cortado: sempre desenhamos
    # todas as linhas, só encolhemos o espaçamento como último recurso)
    font = ImageFont.truetype(font_path, min_size)
    lines = _wrap(draw, text, font, max_width)
    line_h = max(int(min_size * 1.02), int(max_height / max(len(lines), 1)))
    return font, lines, line_h


def _fit_background(bg: Image.Image, size: int) -> Image.Image:
    """Encaixa a imagem de fundo no quadrado SEM cortar nenhuma parte
    dela (diferente de um "cover crop"): redimensiona mantendo a
    proporção inteira dentro do quadrado e preenche a sobra com uma
    versão desfocada e escurecida da própria imagem (blur letterbox) —
    fica muito mais discreto que uma barra sólida, e garante que um
    ícone/robô perto da borda nunca é cortado."""
    w, h = bg.size
    scale = min(size / w, size / h)
    new_w, new_h = int(w * scale), int(h * scale)
    fitted = bg.resize((new_w, new_h))

    # fundo: a própria imagem, esticada pra cobrir tudo e borrada — evita
    # tarjas pretas sólidas nas bordas quando a proporção não bate 1:1
    backdrop = bg.resize((size, size)).filter(ImageFilter.GaussianBlur(40))
    backdrop = Image.eval(backdrop, lambda p: int(p * 0.55))  # escurece pra não competir com o texto

    canvas = backdrop.copy()
    offset = ((size - new_w) // 2, (size - new_h) // 2)
    canvas.paste(fitted, offset)
    return canvas


def compose_slide(
    background_path: str | Path,
    *,
    kicker: str,
    headline: str,
    footer: str,
    slide_number: int,
    slide_total: int,
    out_path: str | Path,
    size: int = 1080,
) -> str:
    """Recebe uma imagem de fundo (qualquer tamanho) e devolve o slide
    final (quadrado, size x size) com o texto aplicado por cima. Retorna
    o out_path como string.

    Duas garantias, sempre:
    - a imagem de fundo NUNCA é cortada (contain-fit, não cover-crop);
    - o texto NUNCA fica cortado (a fonte encolhe automaticamente até
      caber inteiro no espaço disponível)."""
    try:
        bg = Image.open(background_path).convert("RGB")
    except Exception as exc:
        raise ComposeError(f"Não consegui abrir a imagem de fundo: {exc}") from exc

    bg = _fit_background(bg, size)

    # scrim: escurece a metade de baixo pra garantir contraste do texto,
    # sem esconder a ilustração inteira (metade de cima fica limpa)
    scrim = Image.new("L", (size, size), 0)
    scrim_draw = ImageDraw.Draw(scrim)
    for y in range(size):
        # gradiente: 0 no topo, ~235 no fundo, começando a escurecer em ~40%
        t = max(0, (y / size - 0.35) / 0.65)
        scrim_draw.line([(0, y), (size, y)], fill=int(235 * t))
    black = Image.new("RGB", (size, size), (5, 8, 20))
    bg = Image.composite(black, bg, scrim)

    draw = ImageDraw.Draw(bg)
    margin = int(size * 0.065)

    # pílula do progresso (kicker) — canto superior esquerdo
    f_pill = ImageFont.truetype(_FONT_BOLD, int(size * 0.028))
    pill_text = kicker.upper()
    tw = draw.textlength(pill_text, font=f_pill)
    pad_x, pad_y = int(size * 0.02), int(size * 0.012)
    x0, y0 = margin, margin
    x1, y1 = x0 + tw + pad_x * 2, y0 + int(size * 0.028) + pad_y * 2
    draw.rounded_rectangle([x0, y0, x1, y1], radius=(y1 - y0) // 2, fill=(0, 0, 0, 0), outline=LIME, width=2)
    draw.text((x0 + pad_x, y0 + pad_y - 1), pill_text, font=f_pill, fill=LIME)

    # progresso "N/total" — canto superior direito
    f_prog = ImageFont.truetype(_FONT_BOLD, int(size * 0.026))
    prog_text = f"{slide_number}/{slide_total}"
    pw = draw.textlength(prog_text, font=f_prog)
    draw.text((size - margin - pw, margin + 4), prog_text, font=f_prog, fill=GRAY)

    # footer primeiro (tamanho fixo, menor) pra sabermos quanto espaço sobra pra headline
    max_text_w = size - margin * 2
    footer_f = ImageFont.truetype(_FONT_REG, int(size * 0.028))
    footer_lines = _wrap(draw, footer, footer_f, max_text_w)
    footer_line_h = int(size * 0.038)
    footer_h = len(footer_lines) * footer_line_h

    # headline: auto-shrink garantido — reserva todo o espaço vertical
    # disponível acima do footer e nunca deixa a headline vazar
    available_h = size - margin - footer_h - int(size * 0.05) - margin - int(size * 0.09)
    f_head, lines, line_h = _fit_font_to_box(
        draw, headline,
        font_path=_FONT_BOLD, max_size=int(size * 0.068), min_size=int(size * 0.034),
        max_width=max_text_w, max_height=max(available_h, int(size * 0.08)),
    )
    total_head_h = len(lines) * line_h
    y = size - margin - footer_h - int(size * 0.03) - total_head_h
    for line in lines:
        draw.text((margin, y), line, font=f_head, fill=WHITE)
        y += line_h

    y += int(size * 0.015)
    draw.line([(margin, y), (size - margin, y)], fill=(90, 98, 120), width=1)
    y += int(size * 0.02)
    for line in footer_lines:
        draw.text((margin, y), line, font=footer_f, fill=GRAY)
        y += footer_line_h

    out_path = str(out_path)
    bg.save(out_path, quality=95)
    return out_path


def compose_carousel(
    background_paths: list[str | Path],
    slides_copy: list[dict],
    out_dir: str | Path,
    out_prefix: str = "final",
) -> list[str]:
    """Aplica compose_slide em uma lista de imagens de fundo + textos
    (mesmo tamanho de lista). Retorna os paths finais, na ordem."""
    if len(background_paths) != len(slides_copy):
        raise ComposeError(
            f"Número de imagens ({len(background_paths)}) e de textos "
            f"({len(slides_copy)}) não bate."
        )
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    total = len(background_paths)
    for i, (bg_path, copy) in enumerate(zip(background_paths, slides_copy), start=1):
        out_path = out_dir / f"{out_prefix}_{i}.png"
        compose_slide(
            bg_path,
            kicker=copy["kicker"],
            headline=copy["headline"],
            footer=copy["footer"],
            slide_number=i,
            slide_total=total,
            out_path=out_path,
        )
        results.append(str(out_path))
    return results
