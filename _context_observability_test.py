import os, tempfile, importlib
os.environ['OBS_DB'] = tempfile.mktemp(suffix='.db')
from obs import db
importlib.reload(db); db.init()
from obs.context_observability import estimate_breakdown, breakdown_from_messages, context_limit

b = estimate_breakdown('gpt-4o-mini', 'hello world', {'system': 'rules', 'tools': 0})
assert b['used'] > 0
assert b['system'] > 0
assert b['tools'] == 0
assert b['unattributed'] >= 0
assert context_limit('gpt-4o-mini') == 128000

m = breakdown_from_messages([
    {'role':'system','content':'system rules'},
    {'role':'user','content':'question'},
], 'gpt-4o-mini')
assert m['system'] > 0 and m['conversation'] > 0 and m['tools'] == 0

db.insert_context_snapshot({
    'trace_id':'ctx-test','operation':'test','provider':'openai','model':'gpt-4o-mini',
    'context_limit':128000,'used_tokens':10000,'system_tokens':1000,'tool_tokens':0,
    'conversation_tokens':7000,'unattributed_tokens':2000,'reserve_tokens':21760,
    'input_hash':'samehash','status':'ok','cost_usd':0.01,
})
assert db.recent_context_snapshots(1)[0]['trace_id'] == 'ctx-test'
assert db.duplicate_context_count('samehash') == 1
print('CONTEXT OBSERVABILITY OK')
