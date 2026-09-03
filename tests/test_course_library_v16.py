from pathlib import Path
import hashlib

ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()

def test_saved_course_detail_and_cover_upload_contracts_exist():
    app=(ROOT/'app.py').read_text(encoding='utf-8')
    assert '@app.route("/curso-salvo/<course_id>")' in app
    assert '@app.route("/api/course-cover-upload", methods=["POST"])' in app
    assert 'static" / "images" / "course-covers" / "uploads"' in app

def test_catalog_generated_courses_open_saved_detail():
    html=(ROOT/'templates/catalogo.html').read_text(encoding='utf-8')
    assert "url_for('curso_salvo_page', course_id=curso.id)" in html
    assert 'data-href=' in html

def test_both_save_modals_accept_file_cover():
    yt=(ROOT/'templates/curso.html').read_text(encoding='utf-8')
    material=(ROOT/'templates/curso2_revisar.html').read_text(encoding='utf-8')
    assert 'id="saveCourseImageFile"' in yt
    assert 'id="rvSaveImageFile"' in material
    assert '/api/course-cover-upload' in material
    js=(ROOT/'static/js/app.js').read_text(encoding='utf-8')
    assert '/api/course-cover-upload' in js

def test_saved_course_page_renders_complete_course_sections():
    html=(ROOT/'templates/curso_salvo.html').read_text(encoding='utf-8')
    for term in ['curso.video_file','curso.clips','curso.quiz','curso.roadmap','curso.lessons','aula.video_url','aula.audio_url','aula.podcast_url']:
        assert term in html

def test_youtube_pipeline_files_not_changed_by_v16():
    # hashes capturados da V15 imediatamente antes das mudanças da V16.
    # pipelines.py: hash atualizado 2x, ambas mudanças pedidas e
    # intencionais (não é a V16 mexendo sem querer) — instrumentação de
    # performance (obs/stage_timer.py em cada etapa — Download/
    # Transcrição/IA Viral/Corte/Vertical) e depois a indexação do RAG
    # deixando de bloquear o pipeline (roda em background thread agora).
    # Os outros 3 continuam travados, confirmados intocados.
    expected={
        'pipelines.py':'221362c523a3e26a29755273d5b9d1d31d5c251d002588e32c0c1b3986a3f04d',
        'tools/video_splitter.py':'36b0a9672f746cf6d6b90dfc9fea33f5915b8e4ba03cb3aaa5d8d82dcc204122',
        'tools/video_downloader.py':'a8a86169913ceb76eb93fdbf0b2cc68b4340aa8b3f752c77587373ce5d56e174',
        'tools/audio_extractor.py':'75ad0ab5b5d6d64aa3069d731a816a4a854bcb25ef6f6ad9d6b9f307ec834973',
    }
    for path,want in expected.items():
        assert sha(path)==want
