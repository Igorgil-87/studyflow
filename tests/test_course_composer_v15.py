from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_course2_composer_has_include_controls_and_final_save():
    html = (ROOT / 'templates' / 'curso2_revisar.html').read_text(encoding='utf-8')
    assert 'Incluir no curso' in html
    assert 'Salvar curso completo' in html
    assert "add_tutor_note" in html
    assert '/inclusao' in html


def test_course2_media_is_rehydrated_after_reload():
    html = (ROOT / 'templates' / 'curso2_revisar.html').read_text(encoding='utf-8')
    assert 'restaurarMidiasAula' in html
    assert 'aula.video_url' in html
    assert 'conteudo.podcast_url' in html


def test_course2_save_route_and_stable_media_folder_exist():
    app = (ROOT / 'app.py').read_text(encoding='utf-8')
    assert '/api/curso2/<course_id>/salvar' in app
    assert 'videos" / "saved_courses"' in app
    assert 'audios" / "saved_courses"' in app
    assert '_curso2_cover_image' in app


def test_store_supports_editorial_inclusions():
    store = (ROOT / 'curso' / 'store.py').read_text(encoding='utf-8')
    assert 'CREATE TABLE IF NOT EXISTS lesson_inclusions' in store
    assert 'def get_lesson_inclusion' in store
    assert 'def save_lesson_inclusion' in store


def test_video_job_resolves_real_lessons_not_mindmap():
    html = (ROOT / 'templates' / 'curso2_revisar.html').read_text(encoding='utf-8')
    app = (ROOT / 'app.py').read_text(encoding='utf-8')
    resolver = html.split('function _resolverLessonId', 1)[1].split('function _dispararJobComProgresso', 1)[0]
    assert "'/api/curso2/' + courseId + '/licoes'" in resolver
    assert '/mapa-mental' not in resolver
    assert '/api/curso2/<course_id>/licoes' in app
