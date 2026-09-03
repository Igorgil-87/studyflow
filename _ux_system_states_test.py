from pathlib import Path
R=Path(__file__).parent
t=(R/'templates/trends.html').read_text()
j=(R/'static/js/trends.js').read_text()
c=(R/'static/css/style.css').read_text()
assert 'ux-system-state-error' in t and 'gtRetryBtn' in t and 'gtErrorMessage' in t
assert "setAttribute('aria-busy', 'true')" in j and "$('gtRetryBtn')?.addEventListener('click', startAnalysis)" in j
assert 'UX SPRINT 12 · SYSTEM STATES' in c
assert 'ux-inline-system-error' in (R/'templates/curso.html').read_text()
print('UX SYSTEM STATES SPRINT 12 OK')
