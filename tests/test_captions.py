"""tests/test_captions.py — testa tools/captions.py (geração de SRT a
partir de segmentos com timestamp por palavra ou fallback linear)."""

import importlib.util
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_captions():
    """Importa direto do arquivo, contornando tools/__init__.py (que
    carrega Whisper/yt-dlp/moviepy só por tabela — ver test_anti_slop.py
    pra explicação completa). captions.py não depende de nada disso."""
    spec = importlib.util.spec_from_file_location(
        "captions", _PROJECT_ROOT / "tools" / "captions.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_captions = _load_captions()
build_srt = _captions.build_srt
CaptionsError = _captions.CaptionsError


def test_build_srt_com_timestamp_por_palavra():
    """Com timing por palavra, os blocos de legenda respeitam o recorte
    do clip e ficam com o tempo relativo (0 = início do clip)."""
    full_segments = [
        {"text": "isso e um teste de legenda", "start": 10.0, "end": 12.0,
         "words": [
            {"word": "isso", "start": 10.0, "end": 10.3},
            {"word": "e", "start": 10.3, "end": 10.4},
            {"word": "um", "start": 10.4, "end": 10.6},
            {"word": "teste", "start": 10.6, "end": 11.0},
            {"word": "de", "start": 11.0, "end": 11.1},
            {"word": "legenda", "start": 11.1, "end": 11.6},
         ]},
    ]
    srt = build_srt(full_segments, clip_start=10.0, clip_end=13.0)

    assert srt.startswith("1\n")
    assert "00:00:00,000" in srt  # primeiro timestamp sempre começa em 0 (relativo ao clip)
    assert "isso" in srt


def test_build_srt_ignora_segmento_fora_do_clip():
    """Um segmento totalmente fora de [clip_start, clip_end] não deve
    aparecer na legenda."""
    full_segments = [
        {"text": "dentro do clip", "start": 5.0, "end": 6.0,
         "words": [{"word": "dentro", "start": 5.0, "end": 5.5},
                   {"word": "do", "start": 5.5, "end": 5.6},
                   {"word": "clip", "start": 5.6, "end": 6.0}]},
        {"text": "fora do clip completamente", "start": 100.0, "end": 102.0,
         "words": [{"word": "fora", "start": 100.0, "end": 100.5}]},
    ]
    srt = build_srt(full_segments, clip_start=0.0, clip_end=10.0)

    assert "dentro" in srt
    assert "fora" not in srt


def test_build_srt_fallback_sem_timestamp_por_palavra():
    """Sem 'words' no segmento (transcrição sem word_timestamps), o
    fallback de interpolação linear ainda gera legenda válida."""
    full_segments = [
        {"text": "frase sem timing detalhado de palavra", "start": 0.0, "end": 4.0},
    ]
    srt = build_srt(full_segments, clip_start=0.0, clip_end=5.0)

    assert "frase" in srt
    assert "-->" in srt  # tem pelo menos um bloco de timestamp válido


def test_build_srt_levanta_erro_sem_palavras_no_intervalo():
    """Se não sobrar nenhuma palavra dentro do intervalo pedido, levanta
    CaptionsError em vez de devolver um SRT vazio silenciosamente."""
    full_segments = [
        {"text": "algo", "start": 50.0, "end": 51.0, "words": []},
    ]
    try:
        build_srt(full_segments, clip_start=0.0, clip_end=5.0)
        assert False, "deveria ter levantado CaptionsError"
    except CaptionsError:
        pass


def test_legendas_nao_atravessam_silencio_longo():
    """Regressão: um bloco de legenda não deve continuar 'grudado' na
    tela atravessando uma pausa de fala longa (bug real encontrado e
    corrigido em 30/07/2026)."""
    full_segments = [
        {"text": "primeira frase antes da pausa", "start": 0.0, "end": 1.0,
         "words": [{"word": "oi", "start": 0.0, "end": 1.0}]},
        {"text": "segunda frase depois de um silencio longo", "start": 10.0, "end": 11.0,
         "words": [{"word": "tchau", "start": 10.0, "end": 11.0}]},
    ]
    srt = build_srt(full_segments, clip_start=0.0, clip_end=12.0)

    # os dois blocos existem separados (numerados "1" e "2"), não
    # viraram um bloco só esticado por 10 segundos de silêncio
    assert "1\n" in srt
    assert "2\n" in srt
