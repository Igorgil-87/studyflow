from pathlib import Path
js=Path('static/js/trends.js').read_text()
css=Path('static/css/style.css').read_text()
app=Path('app.py').read_text()
assert '_trendDetailModal' in js
for text in ['Resumo','Por que olhar para este assunto?','Fontes para conferir','Uma forma de abordar','Síntese da IA','Ideia sugerida pela IA']:
    assert text in js, text
for event in ['trend_opened','trend_sources_opened','trend_create_content_clicked']:
    assert event in js and event in app, event
assert 'role', 'dialog'
assert '.ux-trend-modal' in css
print('UX TREND DETAIL SPRINT 7 OK')
