from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
COURSO_HTML = (ROOT / "templates/curso.html").read_text(encoding="utf-8")


def test_course_front_renders_full_result_without_approval_step():
    # Decisão dela (comentário no próprio app.js): "YouTube volta ao fluxo
    # completo original: o harness termina toda a geração (vídeo,
    # aulas/cortes, quiz, flashcards e roteiro) e entrega o curso pronto
    # nesta mesma experiência, sem etapa de aprovação." — ou seja, ela
    # tentou a unificação com a tela de revisão do Course Engine (versão
    # anterior deste teste) e decidiu voltar atrás. Este teste valida o
    # estado atual: o listener 'complete' chama renderQuiz/renderVideo/
    # renderClips diretamente, sem redirecionar pra /curso2/.../revisar.
    assert "renderQuiz(quiz, topic);" in APP_JS
    assert "renderVideo(video_file);" in APP_JS
    assert "renderClips(clips);" in APP_JS


def test_course_front_does_not_auto_restore_stale_course():
    # A restauração automática introduzida nos hotfixes fazia /curso abrir
    # bloqueado no último resultado e foi removida para recuperar o fluxo
    # comprovadamente funcional do módulo YouTube.
    assert "restoreGeneratedCourse" not in APP_JS
    assert "persistGeneratedCourse" not in APP_JS


def test_current_course_template_still_has_all_legacy_js_targets():
    required_ids = [
        "topic", "generateBtn", "composer", "pipeline", "result", "errorBox",
        "videoCard", "videoPlayer", "videoEl", "videoTitle", "videoSub",
        "flashcards", "questions", "flashcardsView", "questoesView",
        "roteiroView", "aulasView", "resetBtn", "newBtn",
    ]
    missing = [i for i in required_ids if f'id="{i}"' not in COURSO_HTML]
    assert not missing, f"IDs esperados pelo app.js ausentes no curso.html: {missing}"
