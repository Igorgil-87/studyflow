from pathlib import Path

splitter = Path('tools/video_splitter.py').read_text()
pipeline = Path('pipelines.py').read_text()
env = Path('.env.example').read_text()

assert '_smart_copy' not in splitter
assert 'stable_reencode_v49' in splitter
assert 'perf_job_id' in splitter
assert 'cut_item' in splitter and 'cut_mode' in splitter
assert 'valid_count' in splitter and 'error_count' in splitter
assert 'jobs.set(job_id, "clip_errors"' in pipeline
assert 'jobs.set(job_id, "clips", valid_clips)' in pipeline
assert 'Nenhum clip foi gerado' in pipeline
assert 'SMART_CUT=0' in env
print('PERFORMANCE V49 STABILITY ROLLBACK OK')
