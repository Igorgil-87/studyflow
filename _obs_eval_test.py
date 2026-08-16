import os, tempfile, json
_fd, _tmpdb = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["OBS_DB"] = _tmpdb
from obs import db, judge, report
db.init()

# 1) judge com caller stub (sem LLM real) → parseia JSON e persiste
def good_caller(prompt, model):
    return '{"groundedness":0.9,"relevance":0.85,"coherence":0.8,"hallucination":false,"judge_score":0.86,"rationale":"coerente"}'
v = judge.run_quiz_eval("jobX", "transcript sobre redes neurais", {"flashcards":[]}, _caller=good_caller)
assert v["ok"] and v["judge_score"]==0.86, v
print("judge (stub) OK:", {k:v[k] for k in ('groundedness','judge_score','ok')})

# 2) judge fail-open: caller que explode → veredito neutro, sem exceção
def bad_caller(prompt, model):
    raise RuntimeError("LLM caiu")
v2 = judge.judge_quiz("t", {"x":1}, _caller=bad_caller, trace_id="jobX")
assert v2["ok"] is False and v2["judge_score"] is None
print("judge fail-open OK:", v2["rationale"])

# 3) feedback + summary agregado
db.insert_feedback("jobX","quiz",1,"bom")
db.insert_feedback("jobX","quiz",1,"")
db.insert_feedback("jobX","quiz",-1,"")
s = report.summary()
print("summary.totals:", s["totals"])
print("summary.feedback:", s["feedback"])
print("summary.evals:", s["evals"])
assert s["feedback"]["up"]==2 and s["feedback"]["down"]==1
assert abs(s["feedback"]["ratio"]-0.667)<0.01
assert s["evals"]["count"]>=1
assert s["totals"]["calls"]>=2   # 1 judge ok + 1 judge fail (traçados)
print("\nEVALS + REPORT OK ✅")
