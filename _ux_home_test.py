from pathlib import Path
h=Path('templates/home.html').read_text()
c=Path('static/css/style.css').read_text()
a=Path('app.py').read_text()
d=Path('obs/db.py').read_text()
for text in ['CONTINUE DE ONDE PAROU','O que você quer fazer','APRENDER','CRIAR','ENCONTRAR OPORTUNIDADES','Explorar tendências']:
    assert text in h, text
assert 'href="/trends"' in h
assert "fetch('/api/curso-atual')" in h
for ev in ['home_view','continue_learning_click','learn_click','create_click','trends_click']:
    assert ev in h and ev in a, ev
assert '/api/ux/events' in a
assert 'CREATE TABLE IF NOT EXISTS ux_events' in d
assert 'homeux-paths' in c and ':focus-visible' in c
assert '@media (max-width:639px)' in c and 'prefers-reduced-motion' in c
print('UX HOME SPRINT 2 OK ✅')
