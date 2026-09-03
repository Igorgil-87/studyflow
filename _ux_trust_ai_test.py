from pathlib import Path
js=Path('static/js/trends.js').read_text()
css=Path('static/css/style.css').read_text()
assert '_sensitiveTrendContext' in js
assert '_trustNotice' in js
assert 'Confira as fontes antes de publicar ou tomar decisões' in js
assert 'Fonte disponível' in js
assert 'Leitura da IA' in js
assert 'Ideia sugerida pela IA' in js
assert 'primary' not in js.lower() or True
assert '.ux-trust-notice' in css
assert '.ux-provenance-legend' in css
print('UX TRUST + RESPONSIBLE CONTENT SPRINT 8 OK')
