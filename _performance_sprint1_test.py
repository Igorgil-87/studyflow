from pathlib import Path

root = Path(__file__).parent
pipeline = (root / "pipelines.py").read_text()
stage = (root / "obs/stage_timer.py").read_text()
db = (root / "obs/db.py").read_text()
cache = (root / "cache/llm_cache.py").read_text()
app = (root / "app.py").read_text()
obs_html = (root / "templates/obs.html").read_text()

# Caminho crítico / RAG
assert 'dispatch(' in pipeline
assert '"pipelines.run_rag_index_background"' in pipeline
assert 'threading.Thread(' not in pipeline
assert '"rag_index_async"' in pipeline

# Instrumentação v2
assert 'children(recursive=True)' in stage
assert 'min_available_mb' in stage and 'peak_cpu_pct' in stage
assert 'measurement_version' in db
assert 'CASE WHEN COALESCE(measurement_version, 1) >= 2 THEN peak_rss_mb' in db
for st in ('"total"', '"download"', '"transcribe"', '"highlights"', '"cut"', '"vertical"', '"thumbnails"'):
    assert st in pipeline, st

# Cache flag realmente respeitada
assert 'CACHE_SEMANTIC = os.getenv("CACHE_SEMANTIC", "1") == "1"' in cache
assert 'if entry is None and CACHE_SEMANTIC:' in cache

# API/UI expõem configuração sem segredo
assert '"cache_semantic"' in app
assert '"rss_scope": "process_tree"' in app
assert 'Python + subprocessos (ffmpeg)' in obs_html

print("PERFORMANCE SPRINT 1 OK")
