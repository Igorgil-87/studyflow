import os, tempfile
from pathlib import Path

_tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
_tmp.close()
os.environ['OBS_DB'] = _tmp.name
os.environ['QUALITY_MIN_SAMPLES'] = '3'

from obs import db, quality, report

db.init()

good = {
    'groundedness': .95, 'relevance': .93, 'source_fidelity': .96,
    'completeness': .90, 'judge_score': .94, 'hallucination': False,
}
assert quality.evaluate_verdict(good)['passed'] is True
bad = dict(good, groundedness=.50, hallucination=True)
g = quality.evaluate_verdict(bad)
assert g['passed'] is False and 'groundedness' in g['failures'] and 'hallucination' in g['failures']

# Ainda não há evidência suficiente.
assert quality.aggregate()['status'] == 'insufficient_data'

for i in range(3):
    db.insert_eval({
        'trace_id': f't{i}', 'target': 'rag_answer', 'groundedness': .95,
        'relevance': .93, 'coherence': .92, 'source_fidelity': .96,
        'completeness': .90, 'hallucination': False, 'judge_score': .94,
        'model': 'judge-test', 'prompt_version': 'eval-v2', 'rationale': 'ok'
    })
q = quality.aggregate()
assert q['status'] == 'pass' and q['passed'] is True and q['samples'] == 3

db.insert_benchmark({
    'suite':'s1', 'case_id':'c1', 'label':'Caso 1', 'target':'rag_answer',
    'trace_id':'bench-1', 'judge_model':'judge-test', 'prompt_version':'eval-v2',
    **good, 'gate_status':'pass', 'gate_failures':[]
})
b = report.benchmark_summary()
assert b['count'] == 1 and b['pass_rate'] == 1.0
assert report.recent_benchmarks(5)[0]['suite'] == 's1'

Path(_tmp.name).unlink(missing_ok=True)
print('QUALITY GATES + BENCHMARK OK')
