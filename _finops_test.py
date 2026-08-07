import os, tempfile, time
os.environ["OBS_DB"] = tempfile.mktemp(suffix=".db")
from obs import db, report

db.init()
now = time.time()
# traces variados: quiz, rag_answer, topic_relevance, um erro, um cache_hit
rows = [
    {"trace_id":"a","ts":now,"operation":"quiz","provider":"openai","model":"gpt-4o-mini","latency_ms":900,"status":"ok","input_tokens":1000,"output_tokens":300,"cost_usd":0.0009,"error":None},
    {"trace_id":"b","ts":now,"operation":"rag_answer","provider":"openai","model":"gpt-4o-mini","latency_ms":1200,"status":"ok","input_tokens":1500,"output_tokens":250,"cost_usd":0.0012,"error":None},
    {"trace_id":"c","ts":now,"operation":"topic_relevance","provider":"openai","model":"gpt-4o-mini","latency_ms":600,"status":"ok","input_tokens":800,"output_tokens":120,"cost_usd":0.0005,"error":None},
    {"trace_id":"d","ts":now,"operation":"highlights","provider":"openai","model":"gpt-4o-mini","latency_ms":1500,"status":"error","input_tokens":0,"output_tokens":0,"cost_usd":0,"error":"timeout"},
    {"trace_id":"e","ts":now,"operation":"quiz","provider":"openai","model":"gpt-4o-mini","latency_ms":0,"status":"cache_hit","input_tokens":0,"output_tokens":0,"cost_usd":0,"error":None},
]
for r in rows: db.insert_trace(r)
db.insert_eval({"trace_id":"a","ts":now,"target":"quiz","groundedness":0.9,"relevance":0.85,"coherence":0.88,"hallucination":False,"judge_score":0.87,"model":"gpt-4o-mini","rationale":"bem fundamentado"})

s = report.summary()
fin = s["finops"]; rag = s["rag"]
print("FinOps total:", fin["total_cost_usd"], "| tokens in/out:", fin["total_in_tokens"], fin["total_out_tokens"])
print("FinOps projeção mês:", fin["projected_month_usd"], "| dias:", fin["days_active"])
print("FinOps por operação:", list(fin["by_operation"].keys()))
assert fin["total_in_tokens"] == 1000+1500+800
assert "quiz" in fin["by_operation"] and "rag_answer" in fin["by_operation"]
assert fin["projected_month_usd"] > 0
print("RAG:", "perguntas", rag["queries"], "| relevância", rag["relevance_calls"], "| custo", rag["cost_usd"], "| p95", rag["p95_ms"])
assert rag["queries"] == 1 and rag["relevance_calls"] == 1
assert rag["cost_usd"] == round(0.0012+0.0005,6)

logs = report.recent_logs(10)
assert len(logs) == 5 and logs[0]["operation"]  # ordenado por ts desc
print("logs:", len(logs), "eventos")
errs = report.errors_recent(10)
assert len(errs) == 1 and errs[0]["error"] == "timeout"
print("erros:", errs[0]["operation"], errs[0]["error"])
evs = report.recent_evals(10)
assert len(evs) == 1 and evs[0]["rationale"] == "bem fundamentado"
print("evals detalhados:", evs[0]["target"], evs[0]["judge_score"])
print("\nFINOPS + RAG + LOGS + JUDGE OK ✅")
