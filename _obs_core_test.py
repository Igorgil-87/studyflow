import os, time, tempfile
_fd, _tmpdb = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["OBS_DB"] = _tmpdb
os.environ["RUN_MODE"] = "inline"

from obs import db, pricing, tracing
from infra.resilience import _RAISE

db.init()

# pricing
c = pricing.estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
assert abs(c - 0.75) < 1e-6, c
print("pricing gpt-4o-mini 1M+1M =", c, "USD  (esperado 0.75) OK")
assert pricing.estimate_tokens("abcd"*100) > 0

# traced_llm: sucesso grava trace ok
def fake_quiz(**kw):
    time.sleep(0.02)
    return '{"tema":"x","flashcards":[1,2,3]}'
r = tracing.traced_llm("openai","quiz","gpt-4o-mini", fake_quiz,
                       trace_id="job1", input_text="transcript longo "*50, timeout=5)
assert "flashcards" in r

# traced_llm: falha com fail-open grava trace error e retorna fallback
def fake_fail(**kw):
    raise RuntimeError("boom")
r2 = tracing.traced_llm("anthropic","trends_synthesize","claude-sonnet-4-6", fake_fail,
                        trace_id="job1", input_text="ctx", timeout=5, fallback={})
assert r2 == {}, r2

rows = db.query("SELECT operation,provider,model,status,input_tokens,output_tokens,cost_usd FROM traces WHERE trace_id=? ORDER BY id",("job1",))
print("traces gravados:")
for r in rows: print("  ", r)
assert len(rows)==2
assert rows[0]["status"]=="ok" and rows[0]["output_tokens"]>0
assert rows[1]["status"]=="error"

# feedback + eval
db.insert_feedback("job1","quiz",1,"bom")
db.insert_feedback("job1","quiz",-1,"")
db.insert_eval({"trace_id":"job1","target":"quiz","groundedness":0.9,"relevance":0.8,
                "coherence":0.85,"hallucination":False,"judge_score":0.85,"model":"gpt-4o-mini"})
fb = db.query("SELECT vote,COUNT(*) n FROM feedback GROUP BY vote")
ev = db.query("SELECT judge_score FROM evals WHERE trace_id=?",("job1",))
print("feedback:", fb, "| evals:", ev)
assert ev[0]["judge_score"]==0.85
print("\nNUCLEO OBS OK ✅")
