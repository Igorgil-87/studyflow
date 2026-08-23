"""tests/test_document_extractor.py — cobre rag/document_extractor.py,
incluindo o suporte a TXT/Markdown que faltava (pedido explícito do
Modo Criativo: "PDF, DOCX, PPTX, TXT, Markdown")."""

import pytest

from rag.document_extractor import extract_text, DocumentExtractionError, SUPPORTED_EXTENSIONS


def test_txt_e_md_estao_em_supported_extensions():
    assert ".txt" in SUPPORTED_EXTENSIONS
    assert ".md" in SUPPORTED_EXTENSIONS


def test_extract_txt_utf8():
    texto = extract_text("material.txt", "Conteúdo em português, com acentuação.".encode("utf-8"))
    assert texto == "Conteúdo em português, com acentuação."


def test_extract_md():
    conteudo = "# Título\n\nParágrafo com **negrito**."
    texto = extract_text("material.md", conteudo.encode("utf-8"))
    assert texto == conteudo


def test_extract_txt_latin1_fallback():
    # arquivo salvo em latin-1 (comum em exports antigos do Windows)
    conteudo_bytes = "café com ção".encode("latin-1")
    texto = extract_text("antigo.txt", conteudo_bytes)
    assert "café" in texto


def test_extract_txt_vazio_falha():
    with pytest.raises(DocumentExtractionError):
        extract_text("vazio.txt", b"   ")


def test_formato_nao_suportado_falha_com_mensagem_clara():
    with pytest.raises(DocumentExtractionError) as exc:
        extract_text("arquivo.exe", b"binario qualquer")
    assert "não suportado" in str(exc.value)


def test_extract_pdf_continua_funcionando(monkeypatch):
    """Garante que adicionar .txt/.md não regrediu o caminho de PDF —
    pypdf é sempre instalado (requirements.txt), então testa de verdade."""
    from pypdf import PdfWriter
    import io

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    # página em branco não tem texto -> deve falhar com a mensagem certa,
    # não com um erro genérico de formato não suportado
    with pytest.raises(DocumentExtractionError) as exc:
        extract_text("vazio.pdf", pdf_bytes)
    assert "não suportado" not in str(exc.value)
