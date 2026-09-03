from pathlib import Path
root=Path(__file__).parent
html=(root/'templates/curso.html').read_text()
js=(root/'static/js/app.js').read_text()
assert 'De onde vem o conteúdo?' in html
assert 'COMO VOCÊ QUER COMEÇAR?' not in html
assert 'Escolha sua fonte de aprendizado' not in html
assert 'O que você quer aprender?' in html
assert 'Criar plano de estudo' in html
assert 'Gerar curso' in html
assert '/api/curso2/criar' in html
assert '/api/curso2/from-youtube/${jobId}' not in js
assert 'renderQuiz(quiz, topic);' in js
assert 'renderRoadmap(roadmap);' in js
assert 'renderVideo(video_file);' in js
print('UX GEORGINA SPRINT 3 OK')
