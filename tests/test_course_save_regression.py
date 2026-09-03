from pathlib import Path


def test_course_save_ui_and_api_contract_present():
    html = Path('templates/curso.html').read_text(encoding='utf-8')
    js = Path('static/js/app.js').read_text(encoding='utf-8')
    app = Path('app.py').read_text(encoding='utf-8')
    assert 'id="saveCourseBtn"' in html
    assert 'id="saveCourseDialog"' in html
    assert "fetch('/api/cursos-salvos'" in js
    assert 'video_file: currentCoursePayload.video_file' in js
    assert 'clips: currentCoursePayload.clips' in js
    assert '@app.route("/api/cursos-salvos", methods=["POST"])' in app
    assert '"cursos_salvos"' in app


def test_saved_media_uses_existing_named_video_volume_path():
    compose = Path('docker-compose.full.yml').read_text(encoding='utf-8')
    app = Path('app.py').read_text(encoding='utf-8')
    assert 'videos_data:/app/static/videos' in compose
    assert '"videos" / "saved_courses" / course_id' in app
    assert 'shutil.copy2' in app


def test_flashcards_are_compact_and_separated_from_questions():
    css = Path('static/css/style.css').read_text(encoding='utf-8')
    assert '.cx-result .cards-grid' in css
    assert 'margin-bottom: 22px' in css
    assert 'min-height: 126px' in css
