from pathlib import Path

root = Path(__file__).parent
html = (root / 'templates/curso.html').read_text(encoding='utf-8')
js = (root / 'static/js/app.js').read_text(encoding='utf-8')

# YouTube: fluxo completo e direto, sem revisão/aprovação intermediária.
assert '<span class="btn-label">Gerar curso</span>' in html
assert "eventSource.addEventListener('complete', (e) =>" in js
for render_call in (
    'renderQuiz(quiz, topic);',
    'renderRoadmap(roadmap);',
    'renderVideo(video_file);',
    'renderClips(clips);',
):
    assert render_call in js, render_call
assert '/api/curso2/from-youtube/${jobId}' not in js
assert "window.location.href = `/curso2/${data.curso.course_id}/revisar`" not in js

# Documento: continua com plano revisável antes da geração pesada.
assert '/api/curso2/criar' in html
assert "window.location.href = '/curso2/' + res.data.curso.course_id + '/revisar';" in html
assert 'Criar plano de estudo' in html
assert 'Revise o plano' in html

# Harness do curso continua visível no fluxo YouTube.
for step in (
    'Buscar no YouTube',
    'Baixar e extrair áudio',
    'Transcrever com Whisper',
    'Gerar quiz com LLM',
    'Montar roteiro de treinamento',
    'Identificar blocos de aulas',
    'Cortar vídeo em aulas',
):
    assert step in html, step

print('YOUTUBE FULL COURSE FLOW RESTORED OK')
