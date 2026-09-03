from pathlib import Path
js=Path('static/js/trends.js').read_text()
css=Path('static/css/style.css').read_text()
assert "function qualitativePotential" in js
assert "label: 'Alto'" in js and "label: 'Médio'" in js and "label: 'Baixo'" in js
segment=js[js.index('function buildOpportunityCard'):js.index('function updateTrendsHeader')]
assert '${potential}/10' not in segment
assert 'Estimativa da IA' in segment
assert 'Não é previsão de desempenho' in segment
assert 'ux-potential-help' in segment
assert '.ux-potential-help:focus-visible' in css
print('UX TRENDS SCORE SPRINT 6 OK ✅')
