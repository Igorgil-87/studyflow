from pathlib import Path
r=Path(__file__).parent
home=(r/'templates/home.html').read_text()
curso=(r/'templates/curso.html').read_text()
trends=(r/'templates/trends.html').read_text()
side=(r/'templates/partials/_sidebar.html').read_text()
js=(r/'static/js/trends.js').read_text()
css=(r/'static/css/style.css').read_text()
for text in (home,curso,trends):
    assert 'ux-skip-link' in text and 'id="mainContent"' in text
assert 'aria-pressed="true"' in trends and 'aria-pressed="false"' in trends
assert "setAttribute('aria-pressed'" in js
assert 'aria-current="page"' in side
assert 'role="menuitem"' in side
assert 'role="alert" aria-live="assertive"' in curso
assert 'for="cxMaterialUrl"' in curso
assert "aria-describedby" in js
assert 'prefers-reduced-motion:reduce' in css
assert 'min-height:44px' in css
assert ':focus-visible' in css
print('UX ACCESSIBILITY SPRINT 10 OK')
