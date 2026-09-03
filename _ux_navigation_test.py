from pathlib import Path

sidebar = Path('templates/partials/_sidebar.html').read_text(encoding='utf-8')
mobile = Path('templates/partials/_mobile_header.html').read_text(encoding='utf-8')
css = Path('static/css/style.css').read_text(encoding='utf-8')

for label in ['Aprender', 'Criar', 'Crescer', 'Criar plano de estudo', 'Cursos', 'Tendências', 'Pergunte ao vídeo']:
    assert label in sidebar, label

for route in ['/curso', '/catalogo', '/trilhas', '/estudio', '/trends', '/youtuber', '/rag', '/crescimento']:
    assert f'href="{route}"' in sidebar, route

# Branding deve ser secundário, não o único nome da tarefa.
assert 'com Georgina' in sidebar
assert 'com Marcos Cezar' in sidebar
assert '>Dashboard<' not in sidebar
assert '>Trends<' not in sidebar
assert 'StudyFlow — Início' in mobile
assert ':focus-visible' in css
print('UX NAVIGATION SPRINT 1 OK ✅')
