from pathlib import Path

ROOT=Path(__file__).parent
home=(ROOT/'templates/home.html').read_text()
curso=(ROOT/'templates/curso.html').read_text()
trends=(ROOT/'templates/trends.html').read_text()
js=(ROOT/'static/js/trends.js').read_text()
css=(ROOT/'static/css/style.css').read_text()

assert 'data-action-level="primary" data-ux-event="continue_learning_click"' in home
assert curso.count('data-action-level="primary"') >= 4
assert 'id="generateBtn"' in curso and 'id="cxCriativoBtn"' in curso
assert 'id="cxMaterialUrlBtn" class="ghost-btn ux-action ux-action-secondary" data-action-level="secondary"' in curso
assert 'data-action-level="tertiary" id="resetBtn"' in curso
assert 'data-action-level="primary" id="analyzeBtn"' in trends
assert trends.count('data-action-level="tertiary"') >= 10
assert 'data-action-level="secondary"' in js and 'data-action-level="primary"' in js
assert '.ux-action-primary' in css and '.ux-action-secondary' in css and '.ux-action-tertiary' in css
print('UX CTA HIERARCHY SPRINT 9 OK')
