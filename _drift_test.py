import os, tempfile
os.environ["OBS_DB"] = tempfile.mktemp(suffix=".db")
import random
random.seed(42)   # determinístico (evita flakiness do seed sintético)
from obs import db, drift
import seed_demo

db.init()
seed_demo.main()   # popula baseline saudável + recente degradada

rep = drift.compute()
print("enough_data:", rep["enough_data"], "| status:", rep["status"])
print("baseline: judge=%s err=%.3f p95=%.0f cost=%.5f halluc=%s" % (
    rep["baseline"]["avg_judge_score"], rep["baseline"]["error_rate"],
    rep["baseline"]["p95_latency_ms"], rep["baseline"]["avg_cost_usd"],
    rep["baseline"]["hallucination_rate"]))
print("recente:  judge=%s err=%.3f p95=%.0f cost=%.5f halluc=%s" % (
    rep["recent"]["avg_judge_score"], rep["recent"]["error_rate"],
    rep["recent"]["p95_latency_ms"], rep["recent"]["avg_cost_usd"],
    rep["recent"]["hallucination_rate"]))
print("\nALERTAS:")
metrics_alerted = set()
for a in rep["alerts"]:
    print(f"  [{a['severity']}] {a['message']}  ({a['metric']}: {a['baseline']}→{a['recent']})")
    metrics_alerted.add(a["metric"])

assert rep["enough_data"], "deveria ter amostras suficientes"
assert rep["status"]=="alert", "degradação deveria gerar alerta"
# esperamos drift em latência, erro, judge e alucinação
for m in ("p95_latency_ms","error_rate","avg_judge_score","hallucination_rate"):
    assert m in metrics_alerted, f"faltou alerta de {m}"

# persistência
rep2 = drift.run_check()
hist = drift.history()
assert len(hist)>=1 and hist[0]["status"]=="alert"
print("\nhistórico persistido:", hist[0])

# cenário saudável: limpa e popula só baseline-like → sem alerta
seed_demo.reset()
import time, random
now=time.time()
for _ in range(40):
    db.insert_trace({"trace_id":"x","ts":now-3600*random.uniform(0,10),"operation":"quiz",
        "provider":"openai","model":"gpt-4o-mini","latency_ms":800,"status":"ok",
        "input_tokens":1000,"output_tokens":300,"cost_usd":0.0009,"error":None})
    db.insert_trace({"trace_id":"x","ts":now-3600*random.uniform(30,50),"operation":"quiz",
        "provider":"openai","model":"gpt-4o-mini","latency_ms":820,"status":"ok",
        "input_tokens":1000,"output_tokens":300,"cost_usd":0.0009,"error":None})
rep3 = drift.compute()
print("\ncenário estável → status:", rep3["status"], "| alertas:", len(rep3["alerts"]))
assert rep3["status"]=="ok", "sem degradação não deveria alertar"
print("\nDRIFT OK ✅")
