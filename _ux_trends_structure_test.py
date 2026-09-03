from pathlib import Path
html=Path('templates/trends.html').read_text()
js=Path('static/js/trends.js').read_text()
assert '<h1>Tendências</h1>' in html
assert 'Encontre assuntos que estão ganhando atenção' in html
assert 'Como esta análise foi feita' in html
assert 'Buscando sinais' in html and 'Comparando sinais' in html and 'Selecionando oportunidades' in html
assert 'TREND<strong>LIVE</strong>' not in html
assert 'MISSION CONTROL' not in html
assert 'Orquestração multi-IA' not in html
for id_ in ['gtPipeline','gtEmpty','gtError','gtResults','gtSummaryCard','gtSummaryText','gtCrossThemes','gtCrossGrid','gtTrendsGrid','trendsHeader','trendsHeaderLabel','trendsHeaderCount','catProgress','analyzeBtn','analyzeBtnLabel','gtCrawlUrls']:
    assert f'id="{id_}"' in html, id_
assert "$('emptyAnalyzeBtn')?.addEventListener('click', startAnalysis);" in js
print('UX TRENDS STRUCTURE SPRINT 4 OK')
