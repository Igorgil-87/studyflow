"""
tools/thumbnail.py — gera uma thumbnail pronta para cada corte.

Duas etapas separadas (de propósito, para testar a composição sem vídeo):
  - best_frame(): escolhe o frame mais NÍTIDO do clip (evita tela preta) — moviepy.
  - compose_thumbnail(): compõe a arte (frame + gradiente + título) — PIL puro.

Fonte: Anton (licença aberta OFL) empacotada em assets/fonts; cai para fontes
do sistema ou a default se faltar. Tudo fail-open: erro → retorna None e o
pipeline segue sem thumbnail.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont, ImageOps

_HERE = os.path.dirname(__file__)
_FONT_CANDIDATES = [
    os.path.join(_HERE, "..", "assets", "fonts", "Anton-Regular.ttf"),
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",   # macOS
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
]

ACCENT = (212, 255, 79)   # verde-limão da identidade


def _load_font(size: int):
    for path in _FONT_CANDIDATES:
        try:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        test = (cur + " " + word).strip()
        if draw.textlength(test, font=font) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def compose_thumbnail(frame: Image.Image, title: str,
                      size: tuple[int, int] = (1280, 720),
                      accent: tuple = ACCENT) -> Image.Image:
    """Compõe a thumbnail: frame em 'cover', gradiente e título em destaque."""
    W, H = size
    img = ImageOps.fit(frame.convert("RGB"), size, method=Image.LANCZOS)

    # gradiente escuro de baixo para cima (legibilidade do texto)
    grad = Image.new("L", (1, H), 0)
    for y in range(H):
        frac = max(0.0, (y - H * 0.40) / (H * 0.60))
        grad.putpixel((0, y), int(215 * min(1.0, frac)))
    alpha = grad.resize(size)
    img = Image.composite(Image.new("RGB", size, (0, 0, 0)), img, alpha)

    draw = ImageDraw.Draw(img)
    title = (title or "").strip().upper()
    if not title:
        return img

    margin = int(W * 0.06)
    max_w = W - 2 * margin
    font_size = int(H / 9)
    font = _load_font(font_size)
    lines = _wrap(draw, title, font, max_w)[:3]

    line_h = int(font_size * 1.12)
    total_h = line_h * len(lines)
    y = H - margin - total_h

    # barra de destaque acima do texto
    bar_y = y - int(H * 0.022)
    draw.rectangle([margin, bar_y, margin + int(W * 0.12), bar_y + int(H * 0.008)],
                   fill=accent)

    stroke = max(2, font_size // 16)
    for ln in lines:
        draw.text((margin, y), ln, font=font, fill=(255, 255, 255),
                  stroke_width=stroke, stroke_fill=(0, 0, 0))
        y += line_h
    return img


def best_frame(clip_path: str, samples: int = 5) -> Image.Image:
    """Escolhe o frame mais nítido (maior variância de gradiente), evitando preto."""
    import numpy as np
    from moviepy.editor import VideoFileClip

    clip = VideoFileClip(clip_path)
    try:
        dur = clip.duration or 1.0
        best, best_score = None, -1.0
        for f in [0.2, 0.35, 0.5, 0.65, 0.8][:samples]:
            arr = clip.get_frame(min(dur * f, max(0.0, dur - 0.1)))
            g = arr.mean(axis=2)
            if g.mean() < 15:               # quase preto → descarta
                continue
            score = float(np.diff(g, axis=1).var() + np.diff(g, axis=0).var())
            if score > best_score:
                best, best_score = arr, score
        if best is None:
            best = clip.get_frame(dur * 0.5)
        return Image.fromarray(best.astype("uint8"))
    finally:
        clip.close()


def generate(clip_path: str, title: str, out_path: str,
             content_type: str = "shorts") -> str | None:
    """Gera e salva a thumbnail. Retorna o caminho ou None (fail-open)."""
    try:
        size = (1080, 1920) if content_type == "shorts" else (1280, 720)
        frame = best_frame(clip_path)
        thumb = compose_thumbnail(frame, title, size)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        thumb.convert("RGB").save(out_path, "JPEG", quality=88)
        return out_path
    except Exception as e:
        print(f"[thumbnail] geração ignorada (seguindo): {e}")
        return None
