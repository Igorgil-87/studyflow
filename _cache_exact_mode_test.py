"""CACHE_SEMANTIC=0 deve impedir chamada de embedding e manter hit exato."""
import json
import os
import tempfile

fd, db_path = tempfile.mkstemp(suffix='.db'); os.close(fd)
tmp_dir = tempfile.mkdtemp()
os.environ['OBS_DB'] = db_path
os.environ['CACHE_ENABLED'] = '1'
os.environ['CACHE_SEMANTIC'] = '0'
os.environ['RUN_MODE'] = 'inline'

from obs import db as obs_db
from cache import store, llm_cache, embeddings
obs_db.init(); store.init()

embed_calls = {'n': 0}
def forbidden_embed(text):
    embed_calls['n'] += 1
    raise AssertionError('embedding não deve ser chamado em CACHE_SEMANTIC=0')
embeddings.embed = forbidden_embed

calls = {'n': 0}
def fake_tool(**kwargs):
    calls['n'] += 1
    p = os.path.join(tmp_dir, f'r{calls["n"]}.json')
    with open(p, 'w') as f:
        json.dump({'n': calls['n']}, f)
    return p

key='highlights|mesma-url|shorts|5|transcript'
a=llm_cache.smart_call('openai','highlights','gpt-4o-mini',fake_tool,
    cache_key=key,result_kind='file',file_dir=tmp_dir,trace_id='a')
b=llm_cache.smart_call('openai','highlights','gpt-4o-mini',fake_tool,
    cache_key=key,result_kind='file',file_dir=tmp_dir,trace_id='b')
assert calls['n'] == 1
assert embed_calls['n'] == 0
assert json.load(open(a)) == json.load(open(b))

# Chave diferente = miss real, ainda sem embedding.
llm_cache.smart_call('openai','highlights','gpt-4o-mini',fake_tool,
    cache_key=key+'x',result_kind='file',file_dir=tmp_dir,trace_id='c')
assert calls['n'] == 2
assert embed_calls['n'] == 0
print('CACHE EXACT-ONLY MODE OK')
