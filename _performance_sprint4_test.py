from pathlib import Path

pipelines = Path('pipelines.py').read_text()
splitter = Path('tools/video_splitter.py').read_text()
concat = Path('tools/video_concat.py').read_text()
vertical = Path('tools/vertical_export.py').read_text()
app = Path('app.py').read_text()

assert 'CLIP_PIPELINE_WORKERS' in pipelines
assert 'max_workers=clip_pipeline_workers' in pipelines
assert 'max_workers: int | None = None' in splitter
assert 'ThreadPoolExecutor(max_workers=max_workers)' in splitter
assert 'VERTICAL_PRESET", "fast"' in pipelines
assert 'preset: str = "fast"' in vertical or 'VERTICAL_PRESET", "fast"' in vertical
assert 'vertical_outro_mode' in pipelines
assert 'fallback_reason' in concat
assert '_VARIANT_LOCKS' in concat
assert 'variant_cache_hit' in concat
assert 'clip_pipeline_workers' in app
print('PERFORMANCE SPRINT 4 CLIP CONCURRENCY OK ✅')
