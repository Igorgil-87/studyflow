"""
certificado.py — gera certificado em PNG (para postar em rede social).

Usa Pillow. Desenha um certificado elegante: fundo escuro premium,
moldura, selo, nome do aluno, curso, data e assinatura StudyFlow.
Retorna os bytes do PNG (o endpoint serve como download/inline).
"""

from __future__ import annotations

import io
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 850  # boa proporção para LinkedIn/Instagram

# paleta (identidade StudyFlow)
BG = (14, 14, 16)
CARD = (22, 22, 26)
LIME = (212, 255, 79)
INK = (244, 243, 240)
INK2 = (155, 154, 150)
INK3 = (95, 94, 91)


def _font(size, bold=False):
    """Fontes com fallback multiplataforma (macOS, Linux, Windows)."""
    candidates = [
        # macOS
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf" if bold
        else "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf" if bold
        else "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        # Windows
        "C:/Windows/Fonts/georgiab.ttf" if bold else "C:/Windows/Fonts/georgia.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    # último recurso: fonte padrão do PIL (sempre existe, mas pequena)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _center_text(draw, y, text, font, fill, cx=W // 2):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw / 2, y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def gerar_certificado_png(nome: str, curso: str, data: str,
                          nota: str | None = None) -> bytes:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # cartão interno com moldura
    m = 40
    d.rounded_rectangle([m, m, W - m, H - m], radius=24, fill=CARD,
                        outline=(40, 40, 46), width=2)
    # borda de acento (cantos lime)
    d.rounded_rectangle([m + 14, m + 14, W - m - 14, H - m - 14],
                        radius=16, outline=LIME, width=2)

    # topo: marca
    _center_text(d, 110, "STUDYFLOW", _font(30, bold=True), LIME)
    _center_text(d, 152, "· academia de conteúdo com IA ·", _font(17), INK3)

    # título
    _center_text(d, 235, "CERTIFICADO DE CONCLUSÃO", _font(40, bold=True), INK)

    # linha
    d.line([(W // 2 - 120, 300), (W // 2 + 120, 300)], fill=LIME, width=3)

    # corpo
    _center_text(d, 350, "Certificamos que", _font(20), INK2)
    _center_text(d, 395, nome or "Aluno(a)", _font(46, bold=True), LIME)
    _center_text(d, 480, "concluiu com êxito o curso", _font(20), INK2)

    # nome do curso (quebra se longo)
    curso_font = _font(30, bold=True)
    curso_txt = curso or "Curso"
    if d.textbbox((0, 0), curso_txt, font=curso_font)[2] > W - 260:
        # quebra em 2 linhas simples
        words = curso_txt.split()
        meio = len(words) // 2
        l1, l2 = " ".join(words[:meio]), " ".join(words[meio:])
        _center_text(d, 525, l1, curso_font, INK)
        _center_text(d, 565, l2, curso_font, INK)
    else:
        _center_text(d, 535, curso_txt, curso_font, INK)

    # rodapé: data + nota + assinatura
    y_foot = 680
    _center_text(d, y_foot, f"Emitido em {data}", _font(18), INK3)
    if nota:
        _center_text(d, y_foot + 30, f"Aproveitamento no quiz: {nota}", _font(18), INK2)

    # selo (círculo lime no canto)
    sx, sy, sr = W - 200, H - 210, 55
    d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], outline=LIME, width=3)
    seal_font = _font(15, bold=True)
    _center_text(d, sy - 22, "STUDY", seal_font, LIME, cx=sx)
    _center_text(d, sy - 2, "FLOW", seal_font, LIME, cx=sx)
    # checkmark DESENHADO (2 linhas), não texto — o glyph "✓" (U+2713) não
    # existe em várias fontes (ex: Times New Roman), vira um quadrado vazio
    # "tofu box" em vez do check. Desenhando como linha, funciona sempre,
    # em qualquer fonte disponível no container.
    cx, cy = sx, sy + 22
    d.line([(cx - 9, cy), (cx - 3, cy + 6), (cx + 10, cy - 8)],
           fill=LIME, width=3, joint="curve")

    out = io.BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out.read()
