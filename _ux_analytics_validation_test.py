from pathlib import Path
root=Path(__file__).parent
app=(root/'app.py').read_text()
js=(root/'static/js/trends.js').read_text()
db=(root/'obs/db.py').read_text()
for e in ['trends_view','trend_filter_used','trend_analysis_completed','trend_analysis_failed']:
    assert e in app and e in js, e
assert '/api/ux/analytics' in app
assert 'def ux_analytics' in db
assert 'content_collected' in db and 'raw_identity_exposed' in db
assert 'SELECT DISTINCT user_key' in db
print('UX ANALYTICS + VALIDATION SPRINT 15 OK')
