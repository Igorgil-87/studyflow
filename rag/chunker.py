"""
rag/chunker.py — agrupa segmentos da transcrição em chunks para indexar.

Junta segmentos consecutivos até atingir um teto de caracteres OU de duração,
preservando os timestamps (start do primeiro, end do último). Puro e testável.
"""

from __future__ import annotations


def chunk_segments(
    segments: list[dict],
    max_chars: int = 600,
    max_seconds: float = 60,
) -> list[dict]:
    chunks: list[dict] = []
    buf: list[str] = []
    start = end = None

    def flush():
        nonlocal buf, start, end
        if buf:
            chunks.append({
                "start": round(float(start), 2),
                "end": round(float(end), 2),
                "text": " ".join(buf).strip(),
            })
        buf, start, end = [], None, None

    for s in segments:
        txt = (s.get("text") or "").strip()
        if not txt:
            continue
        st = float(s.get("start", 0) or 0)
        en = float(s.get("end", st) or st)
        if start is None:
            start = st
        buf.append(txt)
        end = en
        cur_chars = sum(len(t) + 1 for t in buf)
        if cur_chars >= max_chars or (end - start) >= max_seconds:
            flush()

    flush()
    return chunks


def chunk_text(text: str, max_chars: int = 800) -> list[str]:
    """Quebra texto puro (sem timestamp — vindo de PDF/PPTX/DOCX) em
    chunks de até max_chars, tentando cortar em fim de parágrafo/frase
    em vez de no meio de uma palavra. Usado por rag/index.py ->
    index_document(), só pro módulo Curso."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""

    for para in paragraphs:
        candidate = f"{buf}\n\n{para}".strip() if buf else para
        if len(candidate) <= max_chars:
            buf = candidate
            continue
        # parágrafo sozinho já estoura o limite -> quebra por frase
        if buf:
            chunks.append(buf)
            buf = ""
        if len(para) <= max_chars:
            buf = para
            continue
        sentences = para.replace("\n", " ").split(". ")
        sub = ""
        for sent in sentences:
            candidate_sub = f"{sub}. {sent}".strip(". ").strip() if sub else sent
            if len(candidate_sub) <= max_chars:
                sub = candidate_sub
            else:
                if sub:
                    chunks.append(sub)
                sub = sent[:max_chars]  # frase absurdamente longa: corta seco, último recurso
        if sub:
            buf = sub

    if buf:
        chunks.append(buf)
    return chunks
