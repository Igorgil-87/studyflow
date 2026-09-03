"""Regression test: /obs performance endpoint must return JSON, never HTML."""
import os
os.environ.setdefault("SECRET_KEY", "test-secret")

from app import app

client = app.test_client()
with client.session_transaction() as sess:
    sess["logged_in"] = True
    sess["user"] = "perf-test"

resp = client.get('/api/observability/pipeline-stages?pipeline=youtuber&limit=5')
assert resp.status_code == 200, (resp.status_code, resp.get_data(as_text=True)[:300])
assert resp.is_json, resp.content_type
payload = resp.get_json()
assert payload.get('ok') is True, payload
assert isinstance(payload.get('etapas'), list)
assert isinstance(payload.get('recentes'), list)
config = payload.get('config') or {}
for key in ('cache_enabled', 'cache_semantic', 'rag_enabled', 'whisper_model', 'rss_scope', 'measurement_version'):
    assert key in config, (key, config)
assert config['measurement_version'] == 2
assert config['rss_scope'] == 'process_tree'
print('PERFORMANCE OBS ENDPOINT JSON OK ✅')
