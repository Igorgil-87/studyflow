from pathlib import Path
js=Path('static/js/trends.js').read_text()
css=Path('static/css/style.css').read_text()
assert 'buildOpportunityCard' in js
assert 'ux-trend-card' in js and 'ux-trend-card' in css
assert 'Ver análise' in js and 'Criar conteúdo' in js
assert 'Potencial' in js
assert 'gt-scores' not in js[js.index('function buildOpportunityCard'):js.index('function updateTrendsHeader')]
assert 'viral_score' not in js[js.index('function buildOpportunityCard'):js.index('function updateTrendsHeader')]
assert 'polemica_score' not in js[js.index('function buildOpportunityCard'):js.index('function updateTrendsHeader')]
print('UX TRENDS CARDS SPRINT 5 OK')
